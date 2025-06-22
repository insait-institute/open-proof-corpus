import regex
from typing import Optional
from loguru import logger
import re
from fractions import Fraction
from grading.utils import latex2sympy_fixed
from sympy import N, Integer
import sympy
from typing import Any
from enum import Enum
from functools import total_ordering
from grading.parse_manual import manual_mapper, complete_mapper
import numpy as np

@total_ordering
class WarningType(Enum):
    NONE = 0
    MINOR = 1
    POSSIBLE = 2
    MAJOR = 3
    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.value < other.value
        return self.value < other


def parse_grading(text: str):
    pattern = re.compile(r"""Category:\s*(.*?)(?:\s|\n)*Points\s+awarded:\s*(.*?)(?:\s|\n)*Description:\s*(.*?)(?:\s|\n)*(?=Category:|$)""", re.DOTALL | re.VERBOSE)    
    matches = pattern.findall(text)
    
    result = {"points": sum(int(points) for _, points, _ in matches), "details": []}
    
    for title, points, desc in matches:
        result["details"].append({
            "title": title,
            "points": int(points),
            "desc": desc
        })
    
    return result

def remove_inner_boxed(match: str):
    pattern = r"(\\boxed|\\fbox)\{((?:[^{}]|\{(?2)\})*)\}"
    matches = list(regex.finditer(pattern, match))
    if not matches:
        return match
    for m in matches:
        match = match.replace(m.group(0), m.group(2))
    return match

def find_last_boxed_content(text: str, list_answer: bool = False) -> Optional[str]:
    pattern = r"(boxed|fbox)\{((?:[^{}]|\{(?2)\})*)\}"
    matches = list(regex.finditer(pattern, text))
    if not matches:
        return None, WarningType.NONE

    if len(matches) > 1 and list_answer:
        # find all boxed content on the same line (no \n in between) as the last boxed
        split_text = text.split("\n")
        for i in range(len(split_text)-1, -1, -1):
            matches_line = list(regex.finditer(pattern, split_text[i]))
            if len(matches_line) > 0:
                returned_boxed = ",".join([match.group(2) for match in matches_line])
                return remove_inner_boxed(returned_boxed), WarningType.POSSIBLE

    last_match = remove_inner_boxed(matches[-1].group(2))
    return last_match, WarningType.NONE


def extract_boxed_answer(text: str, list_answer: bool = False) -> Optional[str]:
    answer, warning = find_last_boxed_content(text, list_answer)
    if answer is not None:
        return answer, warning
    else:
        return None, warning



def replace_and_or(s: str) -> str:
    """
    1) If 'and/or' (or their \\text{} forms) is NOT right next to a comma
       (ignoring spaces) → replace it by a single ','.
    2) Otherwise (comma already on at least one side) → delete it.
    """
    TOKEN = re.compile(
        r"""
        (?:\\text\s*\{\s*)?      # optional '\text{' and any leading blanks
        (and|or)                 # the word itself
        (?:\s*\})?               # optional closing '}' with any blanks
        """,
        re.I | re.VERBOSE,
    )
    # We build a fresh output string piece-by-piece so that each check
    # uses the **current** comma layout, not the one from the original text.
    out, idx = [], 0
    for m in TOKEN.finditer(s):
        start, end = m.span()
        # copy text *before* the token
        out.append(s[idx:start])

        # look to the left of the token, skipping blanks
        j = start - 1
        while j >= 0 and s[j].isspace():
            j -= 1
        comma_left = (j >= 0 and s[j] == ',')

        # look to the right of the token, skipping blanks
        k = end
        while k < len(s) and s[k].isspace():
            k += 1
        comma_right = (k < len(s) and s[k] == ',')

        # choose replacement
        out.append('' if (comma_left or comma_right) else ',')
        idx = end                     # advance cursor

    out.append(s[idx:])               # tail of string
    return ''.join(out)

def extract_boxed_answer_parse(text: str, parse: bool = True, list_answer: bool = False) -> Optional[int]:
    answer, warning = extract_boxed_answer(text, list_answer)
    if answer is not None:
        if answer.count("=") > 1:
            warning = max(warning, WarningType.MAJOR) # this is a major warning, we should not have more than one "="
        try:
            return sympy.Integer(int(answer)), warning
        except:
            # logger.info(f"Could not parse answer {answer} as integer")
            if parse:
                parsed_answer, warning = parse_answer(answer, list_answer=list_answer)
                return parsed_answer, warning
            return answer, warning
    return None, WarningType.MAJOR

def extract_last_integer(text: str) -> Optional[int]:
    pattern = r"\b\d+\b"
    matches = list(regex.finditer(pattern, text))
    if not matches:
        return None, WarningType.MAJOR
    try:
        return int(matches[-1].group()), WarningType.MAJOR
    except:
        return None, WarningType.MAJOR


def extract_answer(text: str, strict_parsing: bool = True, parse: bool = True, list_answer: bool = False):
    if text is None:
        return None, WarningType.MAJOR
    warning_old = WarningType.NONE
    if text in complete_mapper:
        logger.warning(f"Applying complete mapper to {text}")
        text = complete_mapper[text]
        warning_old = WarningType.MAJOR
    text, warning = replace_unicode(text)
    warning = max(warning, warning_old)
    answer, warning_new = extract_boxed_answer_parse(text, parse, list_answer)
    if isinstance(answer, AnswerList) and len(answer.answers) == 1:
        answer = answer.answers[0]
    warning = max(warning, warning_new)
    if answer is not None or strict_parsing:
        return answer, warning
    
    return extract_last_integer(text)

def parse_answer(s: str, primitive_type: type = None, list_answer: bool = False):
    warning = WarningType.NONE
    if s in manual_mapper:
        logger.warning(f"Applying manual parsing to {s}")
        s = manual_mapper[s]
        warning = WarningType.MAJOR
    s = remove_invalid_characters(s)
    s = remove_outer_brackets(normalize_string(s, list_answer))
    output, warning_new = ParseList.parse("(" + s + ")", primitive_type=primitive_type)
    warning = max(warning, warning_new)
    if output is None:
        logger.warning(f"Could not parse {s}, returning None")
        return None, max(warning, WarningType.MAJOR)
    if len(output) == 1:
        output = output[0]

    if isinstance(output, list) or isinstance(output, tuple):
        output = AnswerList(output)
    return output, warning

def normalize_string(s, list_answer=False):
    s = s.replace(r"\left", "").replace(r"\right", "")
    s = s.replace(r"\Bigl", "").replace(r"\Bigr", "")
    s = s.replace(r"\bigl", "").replace(r"\bigr", "")
    s = s.replace(r"\Big", "").replace(r"\big", "").replace(r"\Large", "").replace(r"\large", "")
    s = remove_aligns(s)
    s = s.replace("[", "(")
    s = s.replace("]", ")")
    s = s.replace("\\{", "(") # sets will be converted to lists
    s = s.replace("\\}", ")") # sets will be converted to lists
    s = s.replace("$", "")
    # remove hline and vline
    s = s.replace(r"\hline", "")
    s = s.replace(r"\vline", "")
    s = s.replace(r"\quad", " ")
    s = s.replace("−", "-")
    s = s.replace("–", "-")
    s = s.replace("·", " \\cdot ")
    s = s.replace("^\\circ", " ")
    s = s.replace("^{\\circ}", " ")
    s = s.replace("\\displaystyle", "")
    # remove \\begin{anything} and \\end{anything}
    if s.endswith("."):
        s = s[:-1]

    if list_answer and s is not None:
        s = replace_and_or(s)

    if not list_answer:
        # replace something of the type integer,integer with integerinteger
        s = re.sub(r"(\d+),(\d+)", r"\1\2", s)
    if list_answer:
        s = s.replace(";", ",")
    # if we see \sqrt 123ea pi\frac -> \sqrt{123ea}pi\frac
    if "\\sqrt " in s:
        s = re.sub(r"\\sqrt\s*([^\s{}]*)", r"\\sqrt{\1}", s)
    # remove everything that appears within \text{...}
    s = re.sub(r"\\text\{.*?\}", "", s)
    # replace \mathrm{...} with ...
    s = re.sub(r"\\mathrm\{(.*?)\}", r" \1 ", s)

    s = s.replace("F_{30}", "832040") # Fibonacci number present in one problem

    if "=" in s:
        s = s.split("=")[-1]
    if r"\in" in s and list_answer:
        s = s.split(r"\in")[-1]

    if "\\approx" in s:
        s = s.split("\\approx")[0]
        if s.endswith("("): # in case it was put in brackets
            s = s[:-1]
    return strip(s)

def remove_outer_brackets(s):
    """
    Removes the outermost matching brackets from the string if they encompass the entire string.
    
    Parameters:
    s (str): The input string potentially wrapped with brackets.
    
    Returns:
    str: The string with the outermost brackets removed if they match and encompass the entire string.
    """
    while True:
        if not s:
            return s
        opening = s[0]
        closing = s[-1]

        if opening == "(" and closing == ")":
            count = 0
            matched = True
            for i, char in enumerate(s):
                if char == opening:
                    count += 1
                elif char == closing:
                    count -= 1
                if count == 0 and i != len(s) - 1:
                    matched = False
                    break

            if matched:
                s = s[1:-1]
                continue
        break

    return s

def remove_aligns(s: str) -> str:
    # This pattern captures:
    #   \begin{align followed by any non-} characters (like align*, alignat, etc.)
    #   then any content (non-greedily) up to
    #   \end{align...} with the same "align" prefix
    pattern = r'\\begin{align[^}]*}(.*?)\\end{align[^}]*}'
    
    # Use a callback to remove '&' from the matched group before returning it
    return re.sub(pattern, lambda m: m.group(1).replace('&', '').replace("\\\\", ""), 
                  s, flags=re.DOTALL)

def replace_unicode(text: str) -> str:
    text_old = text
    text = text.replace("\u23a7", r"\boxed{")
    text = text.replace("\u23ab", r"}")
    text = text.replace("\n\u2502", r"\boxed{")
    text = text.replace("\u2502", r"}")
    text = text.replace("\n\u2503", r"\boxed{")
    text = text.replace("\u2503", r"}")
    text = text.replace("\n\uf8f0", r"\boxed{")
    text = text.replace("\uf8fb", r"}")
    warning = WarningType.NONE if text == text_old else WarningType.POSSIBLE
    text = text.replace("\u221a", r"\sqrt") # these ones are for sure fine, no warning necessary
    text = text.replace("\u00d7", r"\cdot")
    text = text.replace("\u202f", r" ")
    text = text.replace("\u2212", "-")
    text = text.replace("\u03c0", r"\pi")
    return text, warning

def remove_invalid_characters(text):
    text = re.sub(r'\\;', '', text)
    text = re.sub(r'\\:', '', text)
    text = re.sub(r'\\,', '', text)
    text = re.sub(r'\\!', '', text)
    return text

def strip(s: str):
    s = s.strip()
    # be careful with this, it can also remove the "\" in "\begin" if just done with strip
    while s.startswith(r"\n"):
        s = s[2:]
    while s.endswith(r"\n"):
        s = s[:-2]
    while s.startswith("\\ "):
        s = s[2:]
    # if s starts with any thing of the form \\\ and then a bracket, or \\\n and then a bracket, remove it
    while re.match(r"\\{2,}\n?\(", s):
        s = s[3:]
    return s

def check_answers(ans1, ans2):
    if ans1 is None or ans2 is None:
        return False
    if (type(ans1) in [list, AnswerList]) != (type(ans2) in [list, AnswerList]):
        return False
    try:
        if not (hasattr(ans1, 'equals') and callable(ans1.equals)) \
            or not (hasattr(ans2, 'equals') and callable(ans2.equals)):
            # do approximate equal here
            if isinstance(ans1, str) or isinstance(ans2, str):
                return bool(ans1 == ans2)
            if abs(ans1 - ans2) < 10 ** -10:
                return True 
            return False
        return bool(ans1.equals(ans2))
    except Exception as e:
        return False

class AnswerList:
    def __init__(self, answers: list[Any]):
        if not isinstance(answers, list) and not isinstance(answers, tuple):
            raise ValueError(f"Expected passed answers to be list or tuple, received {type(answers)}")
        
        valid_answers = []
        for answer in answers:
            if bool(re.search(r'\d', str(answer))):
                valid_answers.append(answer)
            else:
                logger.warning(f'Could not find any numbers in {answer}, removed from list')

        self.answers = list(valid_answers)

    def equals(self, other: list[Any]):
        if len(self.answers) != len(other):
            # logger.info(f"Lists {self.answers} and {other} do not have the same length.")
            return False
        
        match_ids = set()
        for ans1 in self.answers:
            match_found = False
            for i, ans2 in enumerate(other):
                if i not in match_ids and check_answers(ans1, ans2):
                    match_ids.add(i)
                    match_found = True
                    break
            if not match_found:
                # logger.info(f"Could not find a match for element {ans1} in {other}")
                return False
        return True
    
    def __str__(self):
        return '[' + ','.join([str(ans) for ans in self.answers]) + ']'
    
    def __len__(self):
        return len(self.answers)
    
    def __iter__(self):
        return iter(self.answers)

class ParseObject:
    @classmethod
    def is_at_start(cls, string):
        return False

    @classmethod
    def is_complete(cls, string):
        return string.count("{") == string.count("}") and string.count("(") == string.count(")")

    @classmethod
    def is_finished(cls, string):
        return True
    
    @classmethod
    def parse(cls, string):
        raise NotImplementedError
    
class ParsePrimitive(ParseObject):
    @classmethod
    def parse(cls, string, primitive_type):
        warning = WarningType.NONE
        # Integer
        if string.isdigit():
            if primitive_type == Fraction:
                return Fraction(int(string), 1)
            return int(string), warning
        # Float
        try:
            float_string = float(string)
            if int(float_string) == float_string:
                if primitive_type == Fraction:
                    return Fraction(int(float_string), 1)
                return int(float_string), warning
            return float_string, warning
        except ValueError:
            # logger.info(f"Couldn't configure floating point to fraction for {string}")
            pass
        # Expression
        if bool(re.search(r'sqrt(\d+)', string)):
            string = re.sub(r'sqrt(\d+)', r'sqrt{\1}', string)
        if bool(re.search(r"frac(\d)", string)):
            string = re.sub(r'frac(\d)', r'frac{\1}', string)
        try:
            latex_str = string
            for _ in range(5):
                init_str = latex_str
                latex_str = re.sub(r'\\*(?:dfrac|tfrac|frac)\{([^{}]*)\}\{([^{}]*)\}', r'(\1)/(\2)', latex_str)
                latex_str = re.sub(r'\\*binom\{([^{}]*)\}\{([^{}]*)\}', r'binomial(\1, \2)', latex_str)
                latex_str = re.sub(r'\\*sqrt\[(.*?)\]\{(.*?)\}', r'(\2)**(1/(\1))', latex_str)
                latex_str = re.sub(r'\\*sqrt\{(.*?)\}', r'(\1)**(1/2)', latex_str)
  
                latex_str = latex_str.replace('^', '**')
                latex_str = latex_str.replace('\\cdot', '*').replace('\\times', '*')
                latex_str = latex_str.replace('\\pi', ' pi ').replace('\\e', ' E ').replace('\\i', ' I ').replace(" i ", " I ")

                if init_str == latex_str:
                    break
            
            for _ in range(5):

                init_str = latex_str
                latex_str = re.sub(r'\{(\d+)\}', r'(\1)', latex_str)
                latex_str = re.sub(r'\\*(?:dfrac|tfrac|frac)\{([^{}]*)\}\{([^{}]*)\}', r'(\1)/(\2)', latex_str)
                latex_str = re.sub(r'\\*binom\{([^{}]*)\}\{([^{}]*)\}', r'binomial(\1, \2)', latex_str)
                latex_str = re.sub(r'\\*sqrt\[(.*?)\]\{(.*?)\}', r'(\2)**(1/(\1))', latex_str)
                latex_str = re.sub(r'\\*sqrt\{(.*?)\}', r'(\1)**(1/2)', latex_str)

                latex_str = latex_str.replace('^', '**')
                latex_str = latex_str.replace('\\cdot', '*').replace('\\times', '*')
                latex_str = latex_str.replace('\\pi', ' pi ').replace('\\e', ' E ').replace('\\i', ' I ').replace(" i ", " I ")
                if init_str == latex_str:
                    break
            
            # Handle implcit multiplication
            latex_str = re.sub(r'(\d|(?<![a-zA-Z])[a-zA-Z]{1,2}(?![a-zA-Z]))\(', r'\1*(', latex_str) 
            latex_str = re.sub(r'\)(\d|(?<![a-zA-Z])[a-zA-Z]{1,2}(?![a-zA-Z]))', r')*\1', latex_str)
            latex_str = re.sub(r'(?<=\d)((?<![a-zA-Z])[a-zA-Z]{1,2}(?![a-zA-Z]))', r'*\1', latex_str)
            latex_str = re.sub(r'((?<![a-zA-Z])[a-zA-Z]{1,2}(?![a-zA-Z]))(?=\d)', r'\1*', latex_str)
            latex_str = re.sub(r'\{([^{}]*)\}', lambda m: '[' + m.group(1).replace(',', ', ') + ']', 
                               latex_str)

            string = sympy.sympify(latex_str, 
                                   locals={'binomial': sympy.binomial, 
                                           'pi': sympy.pi, 
                                           'E': sympy.E,
                                           'e': sympy.E,
                                           'I': sympy.I}
                                )

        except Exception as e:
            # logger.warning(f"Couldn't parse {string} with standard LaTeX commands")

            try:
                string_no_eq = string
                if "=" in string_no_eq:
                    # rfind is used to remove the last occurence of "="
                    string_no_eq = string_no_eq[string_no_eq.rfind("=")+1:]
                output_val = latex2sympy_fixed(string_no_eq)

                try:
                    float_val = float(N(output_val, 101))
                    if float_val.is_integer() or float("inf") == float_val or float("-inf") == float_val:
                        return int(N(latex2sympy_fixed(string_no_eq), 50001)), warning # important for large ints
                    return float_val, warning
                except:
                    return output_val, warning
            except Exception as e:
                logger.warning(f"Error: Custom parsing error {e}, {string_no_eq}")
                warning = max(warning, WarningType.MAJOR)
                return None, warning

        return string, warning
        
    @classmethod
    def is_at_start(cls, string):
        return True

class ParseList(ParseObject):
    @classmethod
    def is_at_start(cls, string):
        return string.startswith(r"(")
    
    @classmethod
    def is_finished(cls, string):
        # safe condition for finishing a list
        return string.strip().strip(",").endswith(")")
    
    @classmethod
    def is_complete(cls, string):
        return string.count("(") == string.count(")")
    
    @classmethod
    def never_zero_count(cls, string):
        # says wheter count "(" - count ")" for every string[:i] is never zero
        count = 0
        ever_zero = False
        for char in string:
            if char == "(":
                count += 1
            if char == ")":
                count -= 1
            if count == 0:
                ever_zero = True
        return not ever_zero

    
    @classmethod
    def parse(cls, string, delimiter=[r"\n", ","], primitive_type=None, depth=0):
        if isinstance(delimiter, str):
            delimiter = [delimiter]
        output = []
        if not string.startswith("("):
            return None
        string = string.strip().strip(",")
        if cls.never_zero_count(string[:-1]):
            string = string[1:-1]
        string = strip(string)
        used_delim = delimiter[0]
        for delim in delimiter:
            if delim in string:
                comma_separated = string.split(delim)
                used_delim = delim
                break
        warning = WarningType.NONE
        while len(string) > 0:
            previous_string = string
            comma_separated = string.split(used_delim)
            allowed_objects = [ParseList, ParsePrimitive]
            if depth > 50:
                allowed_objects = [ParsePrimitive]
            for obj in allowed_objects:
                if obj.is_at_start(strip(string)):
                    current_index = 1
                    while not obj.is_complete(strip(used_delim.join(comma_separated[:current_index]))) or \
                        not obj.is_finished(strip(used_delim.join(comma_separated[:current_index]))):
                        current_index += 1
                        if current_index >= len(comma_separated):
                            break
                    if not obj.is_complete(strip(used_delim.join(comma_separated[:current_index]))) or \
                        not obj.is_finished(strip(used_delim.join(comma_separated[:current_index]))):
                        continue
                    
                    if obj == ParseList:
                        parsed, new_warning = obj.parse(strip(used_delim.join(comma_separated[:current_index])), 
                                            primitive_type=primitive_type, depth=depth+1)
                    else:
                        parsed, new_warning = obj.parse(strip(used_delim.join(comma_separated[:current_index])), 
                                    primitive_type=primitive_type)
                    warning = max(warning, new_warning)
                    output.append(parsed)
                    string = strip(used_delim.join(comma_separated[current_index:]))
                    break
            if previous_string == string:
                if depth > 50:
                    logger.error(f"Response {string} reached depth > 50")
                    raise ValueError(f"Failed to parse '{string}'")
                return None, WarningType.MAJOR
        return output, warning



def extract_solution(text: str) -> str:
    start_tag = r'\boxed{'
    start = text.rfind(start_tag)
    if start == -1:
        return "none", WarningType.MAJOR

    i = start + len(start_tag)
    depth = 1
    while i < len(text) and depth:
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
        i += 1

    if depth:                       # never balanced → abort
        return "none", WarningType.POSSIBLE

    sol = text[start + len(start_tag) : i - 1]  # slice inside the braces

    while True:
        new_sol = re.sub(r'\\text\s*\{([^{}]*)\}', r'\1', sol)
        if new_sol == sol:          # nothing left to unwrap
            break
        sol = new_sol

    sol = re.sub(r'\s+', '', sol).lower()
    sol = re.sub(r'[^A-Za-z]', '', sol)
    return sol, WarningType.NONE

def extract_judgement(text, ground_truth, is_binary_text=True, threshold=None):
    answer, warning = extract_solution(text)
    if answer is not None:
        if is_binary_text:
            parsed_answer = re.sub(r'\s+', '', answer).lower()
            if parsed_answer == 'correct':
                return 1, warning
            elif parsed_answer == 'incorrect':
                return 0, warning
            else:
                logger.warning(f'Answer {parsed_answer} could not be parsed as correct or incorrect')
                return 0, max(WarningType.POSSIBLE, warning)
        else:
            try:
                return proof_reward_continuous(answer, ground_truth)
            except:
                return 0, WarningType.MAJOR 
    else:
        return None, WarningType.MAJOR
    
def reward_continuous(extracted_solution):
    if extracted_solution == "none":
        return "none"
    if "%" in extracted_solution:
        extracted_solution = extracted_solution.replace("%", "")
    # remove any non-numeric characters except for the decimal point
    extracted_solution = re.sub(r'[^\d.]', '', extracted_solution)
    if extracted_solution == "." or extracted_solution.count('.') > 1:
        extracted_solution = None
    extracted_solution = float(extracted_solution) if extracted_solution else None
    if extracted_solution is None:
        extracted_solution = 50
    if extracted_solution > 1:
        extracted_solution /= 100
    if extracted_solution < 0:
        extracted_solution = 0
    if extracted_solution > 1:
        extracted_solution = 1
    return extracted_solution

def proof_reward_continuous(extracted_solution, ground_truth):
    extracted_solution = reward_continuous(extracted_solution)

    if extracted_solution == "none":
        return -np.log(0.01), WarningType.NONE

    if ground_truth == 1:
        return -np.log(max(0.01, extracted_solution)), WarningType.NONE
    elif ground_truth == 0:
        return -np.log(max(0.01, 1 - extracted_solution)), WarningType.NONE
    else:
        return -np.log(0.01), WarningType.POSSIBLE
