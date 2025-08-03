from loguru import logger


class ProofAgent:
    def __init__(self, querier, prompts, return_if_not_found=False):
        self.querier = querier
        self.prompts = prompts
        self.total_cost = dict()
        self.return_if_not_found = return_if_not_found

    def extract_detailed_solution(self, solution, marker='Detailed Solution', after=True):
        """
        Extracts the text after '### Detailed Solution ###' from the solution string.
        Returns the substring after the marker, stripped of leading/trailing whitespace.
        If the marker is not found, returns an empty string.
        """
        idx = solution.find(marker)
        if idx == -1:
            logger.debug(f"Marker '{marker}' not found in solution.")
            return ''
        if(after):
            return solution[idx + len(marker):].strip()
        else:
            return solution[:idx].strip()
    
    def verify_solution(self, problem_statement, solution):
        dsol = self.extract_detailed_solution(solution)
        logger.debug("Verifying solution...")

        newst = f"""
======================================================================
### Problem ###

{problem_statement}

======================================================================
### Solution ###

{dsol}

{self.prompts['verification_reminder_prompt']}
"""
        query = [
            {
                "role": "system",
                "content": self.prompts['verification_system_prompt']
            },
            {
                "role": "user",
                "content": newst
            }
        ]
        _, out, cost = list(self.querier.run_queries([query]))[0]
        logger.debug(f"Verification query response: {out}")


        check_correctness = """Response in "yes" or "no". Is the following statement saying the solution is correct, or does not contain critical error or a major justification gap?""" \
                + "\n\n" + out
        query = [
            {"role": "user", "content": check_correctness},
        ]
        _, o, cost2 = list(self.querier.run_queries([query]))[0]
        logger.debug(f"Correctness check response: {o}")

        bug_report = ""

        if("yes" not in o.lower()):
            logger.debug("Verification failed. Extracting bug report.")
            bug_report = self.extract_detailed_solution(out, "Detailed Verification", False)
        else:
            logger.debug("Verification successful.")
        
        return bug_report, o, {
            "output_tokens": cost['output_tokens'] + cost2['output_tokens'],
            "input_tokens": cost['input_tokens'] + cost2['input_tokens'],
            "cost": cost['cost'] + cost2['cost']
        }
    
    def check_if_solution_claimed_complete(self, solution):
        logger.debug("Checking if solution is claimed complete.")
        check_complete_prompt = f"""
Is the following text claiming that the solution is complete?
==========================================================

{solution}

==========================================================

Response in exactly "yes" or "no". No other words.
"""
        query = [
            {"role": "user", "content": check_complete_prompt}
        ]
        _, o, cost = list(self.querier.run_queries([query]))[0]

        is_complete = "yes" in o.lower()
        logger.debug(f"Solution claimed complete: {is_complete}")
        return is_complete, cost
    
    def init_explorations(self, problem_statement, verbose=True):
        logger.debug("Initializing explorations.")
        query = [
            {"role": "system", "content": self.prompts['system_prompt']},
            {"role": "user", "content": problem_statement}
        ]
        _, output1, cost = list(self.querier.run_queries([query]))[0]

        query.append(
            {
                "role": "assistant",
                "content": output1
            }
        )
        query.append(
            {"role": "user",
            "content": self.prompts['self_improvement_prompt']
            }
        )

        _, solution, cost2 = list(self.querier.run_queries([query]))[0]

        
        is_complete, cost_check = self.check_if_solution_claimed_complete(output1)
        
        total_cost = {
            "output_tokens": cost['output_tokens'] + cost2['output_tokens'] + cost_check['output_tokens'],
            "input_tokens": cost['input_tokens'] + cost2['input_tokens'] + cost_check['input_tokens'],
            "cost": cost['cost'] + cost2['cost'] + cost_check['cost']
        }

        if not is_complete:
            logger.debug("Initial solution is not complete. Failing exploration.")
            return None, None, None, None, total_cost
        
        verify, good_verify, cost3 = self.verify_solution(problem_statement, solution)
        total_cost['output_tokens'] += cost3['output_tokens']
        total_cost['input_tokens'] += cost3['input_tokens']
        total_cost['cost'] += cost3['cost']

        return query, solution, verify, good_verify, total_cost
    
    def agent(self, problem_statement):
        logger.debug(f"Starting agent for problem: {problem_statement[:50]}...")
        total_cost = {
            "output_tokens": 0,
            "input_tokens": 0,
            "cost": 0
        }
        query, solution, verify, good_verify, cost = self.init_explorations(problem_statement, True)
        total_cost['output_tokens'] += cost['output_tokens']
        total_cost['input_tokens'] += cost['input_tokens']
        total_cost['cost'] += cost['cost']

        logger.debug(f"Current solution: {solution}")
        
        if (solution is None):
            logger.debug("Agent failed during initialization.")
            return None, total_cost

        error_count = 0
        correct_count = 1
        
        for index_iteration in range(30):
            logger.debug(f"Agent iteration {index_iteration+1}")
            print(f"Number of iterations: {index_iteration}, number of corrects: {correct_count}, number of errors: {error_count}")

            if("yes" not in good_verify.lower()):
                # clear
                correct_count = 0
                error_count += 1

                #self improvement
                logger.debug("Verification failed, attempting self-improvement.")
                # establish a new prompt that contains the solution and the verification
                query = [
                    {"role": "system", "content": self.prompts['system_prompt']},
                    {"role": "user", "content": problem_statement}
                ]
                query.append({
                    "role": "assistant",
                    "content": solution
                })

                query.append({
                    "role": "user",
                    "content": self.prompts['correction_prompt'] + "\n\n" + verify
                })

                _, solution, cost3 = list(self.querier.run_queries([query]))[0]
                total_cost['output_tokens'] += cost3['output_tokens']
                total_cost['input_tokens'] += cost3['input_tokens']
                total_cost['cost'] += cost3['cost']

                is_complete, cost_check = self.check_if_solution_claimed_complete(solution)
                total_cost['output_tokens'] += cost_check['output_tokens']
                total_cost['input_tokens'] += cost_check['input_tokens']
                total_cost['cost'] += cost_check['cost']
                if not is_complete:
                    logger.debug("Corrected solution is not complete. Failed.")
                    return solution if self.return_if_not_found else None, total_cost

            logger.debug("Verifying the current solution.")
            verify, good_verify, cost_verify = self.verify_solution(problem_statement, solution)
            total_cost['output_tokens'] += cost_verify['output_tokens']
            total_cost['input_tokens'] += cost_verify['input_tokens']
            total_cost['cost'] += cost_verify['cost']

            if ("yes" in good_verify.lower()):
                logger.debug("Solution verified.")
                correct_count += 1
                error_count = 0
            else:
                logger.debug("Solution still not correct after verification.")
    
            logger.debug(f"Current solution: {solution}")

            if (correct_count >= 5):
                logger.success("Agent found a solution.")
                return solution, total_cost

            elif (error_count >= 10):
                logger.debug("Agent failed to find a solution after correction attempt.")
                return solution if self.return_if_not_found else None, total_cost

        logger.debug("Agent failed to find a solution within 30 iterations.")
        return solution if self.return_if_not_found else None, total_cost
