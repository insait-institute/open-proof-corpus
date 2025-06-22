from string import Formatter
from loguru import logger
from grading.baselines import VerifierBaseline
class Verifier():
    def __init__(self, system_prompt=None, prompt_template=None, querier=None, strategy=None, **kwargs):
        assert(querier is not None or strategy is not None), "The verifier must define either a model querier or a strategy"
        if querier is not None:
            self.querier = querier
        else:
            self.querier = VerifierBaseline(strategy, **kwargs)
        self.cost = 0
        self.detailed_cost = []
        self.system_prompt = system_prompt
        self.prompt_template = prompt_template
        self.strategy = strategy
    
    def safe_format_prompt(self, problem_statement, model_solution, gt_solution=None):
        fields = {fname for _, fname, _, _ in Formatter().parse(self.prompt_template) if fname}

        if 'gt_solution' in fields:
            assert gt_solution is not None, "'gt_solution' is required by the template but is None"

        data = {
            'problem': problem_statement,
            'solution': model_solution,
        }

        if 'gt_solution' in fields:
            data['gt_solution'] = gt_solution
        
        return self.prompt_template.format(**data)

    def build_query(self, problem_statement, model_solution, gt_solution):
        messages = []
        if self.system_prompt is not None: 
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": self.safe_format_prompt(problem_statement, model_solution, gt_solution)})
        return messages
    
    def build_queries(self, problems):
        """
        Build a list of queries from a list of problems.

        Args:
            problems (list): A list of problem instances.

        Returns:
            list: A list of queries generated from the given problems.
        """
        queries = []
        for problem in problems:
            gt_solution = problem.get('solutions', [])[0]['solution'] if problem.get('solutions', []) else None
            queries.append(self.build_query(problem["problem"], problem["solution"], gt_solution))
        return queries
    
    def add_response(self, query, response):
        if self.strategy is None:
            if isinstance(response, tuple) and response[0] is None:
                query.append({"role": "api_error", "content": str(response[1])})
            else:
                query.append({"role": "assistant", "content": response})
            return query
        else:
            return [{"role": "assistant", "content": response}]
    
    def verify(self, problems):
        """
        Solves the initial round of problems by building queries, running them, and appending responses.

        Args:
            problems (list): A list of problems to be solved.

        Returns:
            list: A list of queries with appended responses from the assistant.
        """
        logger.info("Verifying problems.")
        if self.strategy is None:
            queries = self.build_queries(problems)
        else:
            queries = problems
        self.cost = 0
        self.detailed_cost = [{
            "cost": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        } for _ in range(len(problems))]

        for idx, response, detailed_cost in self.querier.run_queries(queries):
            messages = self.add_response(queries[idx], response)
            self.detailed_cost[idx]["cost"] += detailed_cost["cost"]
            self.detailed_cost[idx]["input_tokens"] += detailed_cost["input_tokens"]
            self.detailed_cost[idx]["output_tokens"] += detailed_cost["output_tokens"]
            yield idx, messages, detailed_cost