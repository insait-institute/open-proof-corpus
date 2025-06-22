from loguru import logger
from ..api import APIQuery
from ..utils import extract_solution
import yaml
import re
import json
import os
import pandas as pd
from .utils import compute_mle_elo
from .judgment import Judgments


class Tournament:
    def __init__(self, problem_statement, judge_prompt, model_config, judgments,
                 n_answers, n_rounds, judge_config=None, first_win_word="first", second_win_word="second"):
        self.judgments = judgments
        self.judge_prompt = judge_prompt
        self.problem_statement = problem_statement
        if judge_config is None:
            judge_config = model_config
        self.judge_config = self.clean_model_config(yaml.safe_load(open(judge_config, "r")))
        self.querier = APIQuery(**self.judge_config)
        self.first_win_word = first_win_word
        self.second_win_word = second_win_word
        self.n_answers = n_answers
        self.model_config = self.clean_model_config(yaml.safe_load(open(model_config, "r")))
        self.model_querier = APIQuery(**self.model_config)
        self.n_rounds = n_rounds
        self.pairing_results = []

    def save_current(self, output_folder):
        if output_folder is None:
            return
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        with open(os.path.join(output_folder, "tournament.json"), "w") as f:
            json.dump(self.to_json(), f, indent=4)
        with open(os.path.join(output_folder, "judgments.json"), "w") as f:
            json.dump(self.judgments.to_json(), f, indent=4)

    def clean_model_config(self, model_config):
        del model_config["human_readable_id"]
        if "date" in model_config:
            del model_config["date"]
        return model_config

    def add_answer(self, answer):
        self.judgments.model_answers.add_model_answer(
            answer
        )

    def run_answers(self):
        current_length = len(self.judgments.model_answers)
        if current_length >= self.n_answers:
            logger.info("Already have enough answers.")
            return
        queries = [
            [{
                "role": "user",
                "content": self.problem_statement
            }] for _ in range(self.n_answers - current_length)
        ]
        results = list(self.model_querier.run_queries(queries))

        for _, output, cost in results:
            self.judgments.model_answers.add_model_answer(
                output,
                cost=cost
            )

    def parse_output(self, output):
        parsed_output = extract_solution(output)
        if parsed_output is None:
            return 0.5
        elif parsed_output == self.first_win_word.lower():
            return 0
        elif parsed_output == self.second_win_word.lower():
            return 1
        else:
            return 0.5
        
    def to_query(self, judgment):
        formatted_prompt = self.judge_prompt.format(
            solution_a=str(self.judgments.model_answers[judgment.first_answer_id]),
            solution_b=str(self.judgments.model_answers[judgment.second_answer_id]),
            problem=self.problem_statement,
        )
        return [
            {
                "role": "user",
                "content": formatted_prompt,
            }
        ]
    
    def run_round(self):
        pairings = self.get_next_round()
        if not pairings:
            return False
        judgments_round = []
        for p1, p2 in pairings:
            judgment = self.judgments.judge(p1, p2)
            judgments_round.append(judgment)
        
        judgments_to_run = [judgment for judgment in judgments_round if judgment.outcome is None]

        if judgments_to_run:
            logger.info(f"Running {len(judgments_to_run)} judgments.")
            # Here you would run the judgments using the judge system
            # For now, we will just simulate the outcomes
            queries = [
                self.to_query(judgment) for judgment in judgments_to_run
            ]

            results = list(self.querier.run_queries(queries))
            for idx, output, cost in results:
                judgment = judgments_to_run[idx]
                judgment.set_outcome(
                    self.parse_output(output),
                    outcome_reasoning=output,
                    cost=cost
                )
        
        self.pairing_results.append([judgment.get_simple() for judgment in judgments_round])
        return True
    
    def run_tournament(self, output_folder=None):
        for _ in range(self.n_rounds):
            logger.info(f"Running round {_ + 1}/{self.n_rounds}")
            self.save_current(output_folder)
            continue_run = self.run_round()
            self.save_current(output_folder)
            if not continue_run:
                break
        
        logger.info("Tournament finished.")
    
    def get_cost(self):
        pairs_done = set()
        judge_cost = 0
        for round_results in self.pairing_results:
            for i, j, _ in round_results:
                if (i, j) in pairs_done:
                    continue
                pairs_done.add((i, j))
                judgment = self.judgments.judge(i, j)
                judge_cost += judgment.cost["cost"]
        answer_cost = 0
        for i in range(self.n_answers):
            answer = self.judgments.model_answers[i]
            answer_cost += answer.cost["cost"]
        return {
            "judge_cost": judge_cost,
            "answer_cost": answer_cost,
            "total_cost": judge_cost + answer_cost
        }
    
    def convert_judgments_to_df(self):
        rows = []
        for round_results in self.pairing_results:
            for judgment in round_results:
                rows.append({
                    "model_a": judgment[0],
                    "model_b": judgment[1],
                    "winner": "model_a" if judgment[2] == 0 else ("model_b" if judgment[2] == 1 else "tie"),
                })
        return pd.DataFrame(rows)
    
    def compute_simple_scores(self, df):
        results = dict()
        for _, row in df.iterrows():
            if row["model_a"] not in results:
                results[row["model_a"]] = 0
            if row["model_b"] not in results:
                results[row["model_b"]] = 0
            if row["winner"] == "model_a":
                results[row["model_a"]] += 1
            elif row["winner"] == "model_b":
                results[row["model_b"]] += 1
            else:
                results[row["model_a"]] += 0.5
                results[row["model_b"]] += 0.5
        return results

    def get_next_round(self):
        raise NotImplementedError("Next round logic is not implemented yet.")

    def to_json(self):
        raise NotImplementedError("Tournament to_json method is not implemented yet.")
    
    def get_winner(self):
        raise NotImplementedError("Winner logic is not implemented yet.")
    
    def get_ranking(self):
        raise NotImplementedError("Ranking logic is not implemented yet.")

class SwissTournament(Tournament):
    def __init__(self, n_rounds, n_answers, round_robin=False, 
                 easy_optimization=False, correct_length_bias=False, 
                 correct_position_bias=False, double_round=False, **kwargs):
        if round_robin:
            n_rounds = 1
        super().__init__(**kwargs, n_rounds=n_rounds, n_answers=n_answers)
        self.round_robin = round_robin
        self.easy_optimization = easy_optimization
        self.correct_length_bias = correct_length_bias
        self.correct_position_bias = correct_position_bias
        self.double_round = double_round

    def convert_judgments_to_df(self):
        rows = []
        for round_results in self.pairing_results:
            for judgment in round_results:
                base_dict = {
                    "model_a": judgment[0],
                    "model_b": judgment[1],
                    "winner": "model_a" if judgment[2] == 0 else ("model_b" if judgment[2] == 1 else "tie"),
                }
                if self.correct_length_bias:
                    base_dict["length_a"] = len(self.judgments.model_answers[judgment[0]].answer) / 1000
                    base_dict["length_b"] = len(self.judgments.model_answers[judgment[1]].answer) / 1000
                if self.correct_position_bias:
                    base_dict["position_a"] = 1
                    base_dict["position_b"] = 0
                rows.append(base_dict)
        return pd.DataFrame(rows)

    def get_ranking(self):
        df = self.convert_judgments_to_df()
        elo, biases = compute_mle_elo(df)
        simple = self.compute_simple_scores(df)

        combined_scores = []
        for answer_index in elo.index:
            combined_scores.append({
                "answer": answer_index,
                "elo": float(elo[answer_index]),
                "simple": simple[answer_index],
            })

        # sort by elo
        combined_scores = sorted(combined_scores, key=lambda x: x["elo"], reverse=True)
        # save to csv
        df = pd.DataFrame(combined_scores)
        return df
    
    def get_winner(self):
        rank = self.get_ranking()
        return rank.iloc[0]["answer"]
    
    def get_next_round(self):
        if self.round_robin:
            pairs = []
            for i in range(self.n_answers):
                for j in range(self.n_answers):
                    if i != j:
                        pairs.append((i, j))
            return pairs
        # Step 1: Calculate scores and player roles
        scores = [0] * self.n_answers
        role_counts = [{'first': 0, 'second': 0} for _ in range(self.n_answers)]
        played_pairs = set()

        for round_result in self.pairing_results:
            for p1, p2, result in round_result:
                if result == 1:
                    scores[p1] += 1
                elif result == 0:
                    scores[p2] += 1
                else:
                    scores[p1] += 0.5
                    scores[p2] += 0.5
                role_counts[p1]['first'] += 1
                role_counts[p2]['second'] += 1
                played_pairs.add(frozenset([p1, p2]))

        # Step 2: Sort players by score (descending)
        players = list(range(self.n_answers))
        players.sort(key=lambda x: -scores[x])
        logger.info(f"Players sorted by score: {players}")
        # Step 3: Greedy matching with fairness
        next_round = []
        used = set()

        while players:
            p1 = players.pop(0)
            if p1 in used:
                continue
            for i, p2 in enumerate(players):
                if frozenset([p1, p2]) not in played_pairs or p2 == max([player for player in players if player not in used]):
                    # Choose roles based on who has fewer games in each role
                    if role_counts[p1]['first'] <= role_counts[p1]['second']:
                        game = (p1, p2)
                    else:
                        game = (p2, p1)

                    next_round.append((game[0], game[1]))
                    used.add(p1)
                    used.add(p2)
                    players.pop(i)
                    break
            else:
                # Odd number of players or couldn't find a match
                # Could assign a bye or skip
                continue
        logger.info(f"Next round pairs: {next_round}")

        if self.easy_optimization:
            rounds_left = self.n_rounds - len(self.pairing_results)
            max_points = max(scores)
            pairs_to_remove = []
            for i, pair in enumerate(next_round):
                p1, p2 = pair
                if scores[p1] + rounds_left + 1 <= max_points and scores[p2] + rounds_left + 1 <= max_points:
                    pairs_to_remove.append(i)
            
            for i in reversed(pairs_to_remove):
                next_round.pop(i)
            logger.info(f"Next round pairs after easy optimization: {next_round}")

        if self.double_round:
            # Add a second round with reversed roles
            for p1, p2 in next_round:
                if (p2, p1) not in next_round:
                    next_round.append((p2, p1))
            logger.info(f"Next round pairs after double round: {next_round}")
        return next_round
    
    def to_json(self):
        return {
            "problem_statement": self.problem_statement,
            "judge_prompt": self.judge_prompt,
            "judge_config": self.judge_config,
            "pairing_results": self.pairing_results,
            "n_rounds": self.n_rounds,
            "n_answers": self.n_answers,
            "first_win_word": self.first_win_word,
            "second_win_word": self.second_win_word,
            "judgments": self.judgments.to_json(),
            "round_robin": self.round_robin,
            "easy_optimization": self.easy_optimization,
            "correct_length_bias": self.correct_length_bias,
            "correct_position_bias": self.correct_position_bias,
            "double_round": self.double_round
        }
    
    @classmethod
    def from_json(cls, json_data):
        return cls(
            problem_statement=json_data["problem_statement"],
            judge_prompt=json_data["judge_prompt"],
            judge_config=json_data["judge_config"],
            n_answers=json_data["n_answers"],
            judgments=Judgments.from_json(json_data["judgments"]),
            first_win_word=json_data["first_win_word"],
            second_win_word=json_data["second_win_word"],
            n_rounds=json_data["n_rounds"],
            round_robin=json_data["round_robin"],
            easy_optimization=json_data["easy_optimization"],
            correct_length_bias=json_data["correct_length_bias"],
            correct_position_bias=json_data["correct_position_bias"],
            double_round=json_data["double_round"],
        )
    

class BracketTournament(Tournament):
    def __init__(self, max_losses, n_answers, **kwargs):
        super().__init__(**kwargs, n_rounds=10 * n_answers, n_answers=n_answers)
        self.max_losses = max_losses
    
    def to_json(self):
        return {
            "problem_statement": self.problem_statement,
            "judge_prompt": self.judge_prompt,
            "judge_config": self.judge_config,
            "pairing_results": self.pairing_results,
            "n_rounds": self.n_rounds,
            "n_answers": self.n_answers,
            "first_win_word": self.first_win_word,
            "second_win_word": self.second_win_word,
            "judgments": self.judgments.to_json(),
            "max_losses": self.max_losses
        }
    
    @classmethod
    def from_json(cls, json_data):
        return cls(
            problem_statement=json_data["problem_statement"],
            judge_prompt=json_data["judge_prompt"],
            judge_config=json_data["judge_config"],
            judgments=Judgments.from_json(json_data["judgments"]),
            first_win_word=json_data["first_win_word"],
            n_answers=json_data["n_answers"],
            second_win_word=json_data["second_win_word"],
            n_rounds=json_data["n_rounds"],
            max_losses=json_data["max_losses"]
        )
    
    def get_next_round(self):
        n_losses = [0] * self.n_answers
        for round_result in self.pairing_results:
            for i, j, result in round_result:
                if result >= 0.5:
                    n_losses[i] += 1
                else:
                    n_losses[j] += 1
        # reverse sort indices by number of losses
        current_ranking = sorted(range(self.n_answers), key=lambda x: n_losses[x])
        logger.info(f"Current ranking: {current_ranking}")
        current_unpaired = []
        current_pairs = []
        for n_loss in range(self.max_losses, -1, -1):
            current_unpaired.extend([i for i, x in enumerate(n_losses) if x == n_loss])
            while len(current_unpaired) > 1:
                i = current_unpaired.pop()
                j = current_unpaired.pop()
                current_pairs.append((j, i))
        current_pairs = self.alternate_first_second(current_pairs)
        logger.info(f"Next round pairs: {current_pairs}")
        return current_pairs
    
    def alternate_first_second(self, pairs):
        counts_first = [0] * self.n_answers
        count_both = [0] * self.n_answers
        for round_pairs in self.pairing_results:
            for i, j, _ in round_pairs:
                counts_first[i] += 1
                count_both[i] += 1
                count_both[j] += 1
        new_pairs = []
        for i, j in pairs:
            if counts_first[i] / max(1, count_both[i]) > counts_first[j] / max(1, count_both[j]):
                new_pairs.append((j, i))
            else:
                new_pairs.append((i, j))
        return new_pairs
    
    def get_winner(self):
        raise NotImplementedError("Winner logic is not implemented yet.")
    
    def get_ranking(self):
        reverse_ranking = []
        n_losses = [0] * self.n_answers
        for round_result in self.pairing_results:
            for i, j, result in round_result:
                if result >= 0.5:
                    n_losses[i] += 1
                    if n_losses[i] > self.max_losses:
                        reverse_ranking.append(i)
                else:
                    n_losses[j] += 1
                    if n_losses[j] > self.max_losses:
                        reverse_ranking.append(j)
        
        reverse_ranking += [i for i in range(self.n_answers) if i not in reverse_ranking]
        reverse_ranking = reverse_ranking[::-1]

        df = self.convert_judgments_to_df()
        elo, _ = compute_mle_elo(df)
        simple = self.compute_simple_scores(df)

        combined_scores = []
        for answer_index in elo.index:
            combined_scores.append({
                "answer": answer_index,
                "elo": float(elo[answer_index]),
                "index": reverse_ranking.index(answer_index),
                "simple": simple[answer_index],
            })

        # sort by ranking
        combined_scores = sorted(combined_scores, key=lambda x: x["index"], reverse=False)
        # save to csv
        df = pd.DataFrame(combined_scores)
        return df