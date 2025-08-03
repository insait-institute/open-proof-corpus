import random
import numpy as np

class ModelAnswers:
    def __init__(self, answers=None, model_has_think=False):
        self.model_has_think = model_has_think
        self.answers = answers if answers is not None else []
        self.costs = []
    
    def clean_answer(self, answer):
        if "</think>" in answer:
            answer = answer.split("</think>")[-1]
        else:
            answer = "Model answer is empty."
        
        return answer
    
    def add_model_answer(self, model_answer, cost):
        if self.model_has_think:
            model_answer = self.clean_answer(model_answer)
        
        self.answers.append(model_answer)
        self.costs.append(cost)
    
    def __getitem__(self, index):
        return self.answers[index]
    
    def __len__(self):
        return len(self.answers)
    
    def to_json(self):
        return {
            "answers": self.answers,
            "model_has_think": self.model_has_think,
        }
    
    @classmethod
    def from_json(cls, json_data):
        return cls(
            answers=[answer for answer in json_data["answers"]],
            model_has_think=json_data["model_has_think"],
        )

class Judgment:
    def __init__(self, first_answer_id, second_answer_id, outcome=None, outcome_reasoning=None, 
                 cost=None, detailed_outcomes=None):
        self.first_answer_id = first_answer_id
        self.second_answer_id = second_answer_id
        self.outcome = outcome
        self.detailed_outcomes = detailed_outcomes if detailed_outcomes is not None else []
        self.outcome_reasoning = outcome_reasoning if outcome_reasoning is not None else []
        self.cost = cost
        if detailed_outcomes is None and outcome is not None:
            self.detailed_outcomes = [outcome]
    
    def __eq__(self, value):
        if isinstance(value, Judgment):
            return (self.first_answer_id == value.first_answer_id and
                    self.second_answer_id == value.second_answer_id)
        else:
            raise ValueError("Cannot compare Judgment with non-Judgment type.")

    def add_outcome(self, outcome, outcome_reasoning=None, cost=None, reversed_order=False):
        if reversed_order:
            outcome = 1 - outcome
        self.detailed_outcomes.append(outcome)
        self.outcome_reasoning.append(outcome_reasoning)
        if self.cost is None:
            self.cost = cost
        else:
            for key in self.cost:
                if key in cost:
                    self.cost[key] += cost[key]
                else:
                    self.cost[key] = cost[key]
        self.outcome = np.mean(self.detailed_outcomes)

    def get_simple(self, max_votes=None):
        if not max_votes:
            max_votes = len(self.detailed_outcomes)
        
        # choose max_votes outcomes
        if len(self.detailed_outcomes) > max_votes:
            indices = np.random.choice(len(self.detailed_outcomes), max_votes, replace=False)
            selected_outcomes = [self.detailed_outcomes[i] for i in indices]
        else:
            selected_outcomes = self.detailed_outcomes
        return [
            self.first_answer_id,
            self.second_answer_id,
            np.mean(selected_outcomes),
            selected_outcomes
        ]

    def to_json(self):
        return {
            "first_answer_id": self.first_answer_id,
            "second_answer_id": self.second_answer_id,
            "outcome": self.outcome,
            "outcome_reasoning": self.outcome_reasoning,
            "detailed_outcomes": self.detailed_outcomes,
            "cost": self.cost
        }
    
    @classmethod
    def from_json(cls, json_data):
        return cls(
            first_answer_id=json_data["first_answer_id"],
            second_answer_id=json_data["second_answer_id"],
            outcome=json_data.get("outcome"),
            outcome_reasoning=json_data.get("outcome_reasoning", []),
            detailed_outcomes=json_data.get("detailed_outcomes", []),
            cost=json_data.get("cost")
        )

class Judgments:
    def __init__(self, model_answers=None, judgments=None):
        self.judgments = judgments if judgments is not None else []
        self.model_answers = model_answers if model_answers is not None else ModelAnswers()

    def judge(self, first_id, second_id, order_independent=False):

        for judgment in self.judgments:
            if judgment.first_answer_id == first_id and judgment.second_answer_id == second_id:
                return judgment
            if order_independent and judgment.first_answer_id == second_id and judgment.second_answer_id == first_id:
                return judgment
        
        # if not found, create a new judgment
        judgment = Judgment(first_id, second_id)
        self.judgments.append(judgment)
        return judgment
    
    def reindex(self):
        random_permutation = list(range(len(self.model_answers.answers)))
        random.shuffle(random_permutation)
        id_mapper = {i: random_permutation[i] for i in range(len(self.model_answers.answers))}
        for judgment in self.judgments:
            judgment.first_answer_id = id_mapper[judgment.first_answer_id]
            judgment.second_answer_id = id_mapper[judgment.second_answer_id]
        
        new_answers = [None for _ in range(len(self.model_answers.answers))]
        for i in range(len(self.model_answers.answers)):
            new_answers[id_mapper[i]] = self.model_answers.answers[i]
            new_answers[id_mapper[i]].id_ = id_mapper[i]
        self.model_answers.answers = new_answers

    def to_json(self):
        return {
            "model_answers": self.model_answers.to_json(),
            "judgments": [judgment.to_json() for judgment in self.judgments],
        }
    
    @classmethod
    def from_json(cls, json_data):
        return cls(
            model_answers=ModelAnswers.from_json(json_data["model_answers"]),
            judgments=[Judgment.from_json(judgment) for judgment in json_data["judgments"]],
        )