# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Tasks' problems """
import gettext
from abc import ABCMeta, abstractmethod

from inginious.common.base import id_checker
from inginious.common.tasks_code_boxes import InputBox, MultilineBox, TextBox, FileBox


class BasicProblem(object, metaclass=ABCMeta):
    """Basic problem """

    @abstractmethod
    def get_type(self):
        """ Returns the type of the problem """
        return None

    @abstractmethod
    def input_is_consistent(self, task_input, default_allowed_extension, default_max_size):
        """ Check if an input for this problem is consistent. Return true if this is case, false else """
        return False

    @abstractmethod
    def check_answer(self, task_input, language):
        """
            Check the answer. Returns four values:
            the first is either True, False or None, indicating respectively that the answer is valid, invalid, or need to be sent to VM
            the second is the error message assigned to the task, if any (unused for now)
            the third is the error message assigned to this problem, if any
            the fourth is the number of errors in MCQ; should be zero when not a MCQ.
        """
        return True, None, None, 0

    @classmethod
    @abstractmethod
    def get_text_fields(cls):
        """ Returns a dict whose keys are the keys of content dict
        and val is True if value of content[key] is human-readable text """
        return {"name": True, "header": True}

    def get_id(self):
        """ Get the id of this problem """
        return self._id

    def get_task(self):
        """ Get the task containing this problem """
        return self._task

    def get_name(self, language=None):
        """ Get the name of this problem """
        return self.gettext(language, self._name) if self._name else ""

    def get_header(self, language=None):
        """ Get the header of this problem """
        return self.gettext(language, self._header) if self._header else ""

    def get_original_content(self):
        """ Get a dict fully describing this sub-problem """
        return dict(self._original_content)

    def __init__(self, task, problemid, content, translations=None):
        if not id_checker(problemid):
            raise Exception("Invalid problem _id: " + problemid)

        self._translations = translations
        self._id = problemid
        self._task = task
        self._name = content['name'] if "name" in content else ""
        self._header = content['header'] if "header" in content else ""
        self._original_content = content

    def gettext(self, language, *args, **kwargs):
        translation = self._translations.get(language, gettext.NullTranslations())
        return translation.gettext(*args, **kwargs)


class MatchProblem(BasicProblem):
    """Display an input box and check that the content is correct"""

    def __init__(self, task, problemid, content, translations=None):
        super(MatchProblem, self).__init__(task, problemid, content, translations)
        if not "answer" in content:
            raise Exception("There is no answer in this problem with type==match")
        self._answer = str(content["answer"])

    def get_type(self):
        return "match"

    def input_is_consistent(self, task_input, default_allowed_extension, default_max_size):
        return self.get_id() in task_input

    def check_answer(self, task_input, language):
        if task_input[self.get_id()].strip() == self._answer:
            return True, None, ["_correct_answer"], 0
        else:
            return False, None, ["_wrong_answer"], 0

    @classmethod
    def get_text_fields(cls):
        return BasicProblem.get_text_fields()


class BasicCodeProblem(BasicProblem):
    """Basic problem with code input. Do all the job with the backend"""

    def __init__(self, task, problemid, content, translations=None):
        super(BasicCodeProblem, self).__init__(task, problemid, content, translations)
        self._boxes = []
        if task.get_environment() is None:
            raise Exception("Environment undefined, but there is a problem with type=code or type=code-single-line")

    def get_boxes(self):
        """ Returns all the boxes of this code problem """
        return self._boxes

    @abstractmethod
    def get_type(self):
        return None

    def input_is_consistent(self, task_input, default_allowed_extension, default_max_size):
        for box in self._boxes:
            if not box.input_is_consistent(task_input, default_allowed_extension, default_max_size):
                return False
        return True

    _box_types = {"input-text": InputBox, "input-decimal": InputBox, "input-integer": InputBox, "multiline": MultilineBox, "text": TextBox,
                  "file": FileBox}

    def _create_box(self, boxid, box_content):
        """ Create adequate box """
        if not id_checker(boxid) and not boxid == "":
            raise Exception("Invalid box _id " + boxid)
        if "type" not in box_content:
            raise Exception("Box " + boxid + " does not have a type")
        if box_content["type"] not in self._box_types:
            raise Exception("Unknown box type " + box_content["type"] + "for box _id " + boxid)

        return self._box_types[box_content["type"]](self, boxid, box_content)

    def check_answer(self, _, __):
        return None, None, None, 0

    @classmethod
    def get_text_fields(cls):
        return BasicProblem.get_text_fields()


class CodeSingleLineProblem(BasicCodeProblem):
    """Code problem with a single line of input"""

    def __init__(self, task, problemid, content, translations=None):
        super(CodeSingleLineProblem, self).__init__(task, problemid, content, translations)
        self._boxes = [self._create_box("", {"type": "input-text", "optional": content.get("optional", False)})]

    def get_type(self):
        return "code-single-line"

    @classmethod
    def get_text_fields(cls):
        return BasicProblem.get_text_fields()


class CodeFileProblem(BasicCodeProblem):
    """Code problem which allow to test a file"""

    def __init__(self, task, problemid, content, translations=None):
        super(CodeFileProblem, self).__init__(task, problemid, content, translations)
        self._boxes = [
            self._create_box("", {"type": "file", "max_size": content.get("max_size", None), "allowed_exts": content.get("allowed_exts", None)})]

    def get_type(self):
        return "code-file"

    @classmethod
    def get_text_fields(cls):
        return BasicCodeProblem.get_text_fields()


class CodeProblem(BasicCodeProblem):
    """Code problem"""

    def __init__(self, task, problemid, content, translations=None):
        super(CodeProblem, self).__init__(task, problemid, content, translations)
        if "boxes" in content:
            self._boxes = []
            for boxid, box_content in content['boxes'].items():
                if boxid == "":
                    raise Exception("Empty box ids are not allowed")
                self._boxes.append(self._create_box(boxid, box_content))
        else:
            if "language" in content:
                self._boxes = [self._create_box("", {"type": "multiline", "language": content["language"],
                                                     "optional": content.get("optional", False)})]
            else:
                self._boxes = [self._create_box("", {"type": "multiline", "optional": content.get("optional", False)})]

    def get_type(self):
        return "code"

    @classmethod
    def get_text_fields(cls):
        return BasicProblem.get_text_fields()


class MultipleChoiceProblem(BasicProblem):
    """Multiple choice problems"""

    def __init__(self, task, problemid, content, translations=None):
        super(MultipleChoiceProblem, self).__init__(task, problemid, content, translations)
        self._multiple = content.get("multiple", False)
        if "choices" not in content or not isinstance(content['choices'], list):
            raise Exception("Multiple choice problem " + problemid + " does not have choices or choices are not an array")
        good_choices = []
        bad_choices = []
        for index, choice in enumerate(content["choices"]):
            data = {"index": index}
            if "text" not in choice:
                raise Exception("A choice in " + problemid + " does not have text")
            data['text'] = choice["text"]
            data['feedback'] = choice.get('feedback')
            if choice.get('valid', False):
                data['valid'] = True
                good_choices.append(data)
            else:
                data['valid'] = False
                bad_choices.append(data)

        if len(good_choices) == 0:
            raise Exception("Problem " + problemid + " does not have any valid answer")

        self._limit = 0
        if "limit" in content and isinstance(content['limit'], int) and content['limit'] >= 0 and (not self._multiple or content['limit'] >= \
                len(good_choices) or content['limit'] == 0):
            self._limit = content['limit']
        elif "limit" in content:
            raise Exception("Invalid limit in problem " + problemid)

        self._centralize = content.get("centralize", False)

        self._error_message = content.get("error_message", None)
        self._success_message = content.get("success_message", None)

        self._choices = good_choices + bad_choices

    def get_type(self):
        return "multiple-choice"

    def allow_multiple(self):
        """ Returns true if this multiple choice problem allows checking multiple answers """
        return self._multiple

    def get_choice_with_index(self, index):
        """ Return the choice with index=index """
        for entry in self._choices:
            if entry["index"] == index:
                return entry
        return None

    def input_is_consistent(self, task_input, default_allowed_extension, default_max_size):
        if self.get_id() not in task_input:
            return False
        if self._multiple:
            if not isinstance(task_input[self.get_id()], list):
                return False
            try:  # test conversion to int
                for entry in task_input[self.get_id()]:
                    if self.get_choice_with_index(int(entry)) is None:
                        return False
            except ValueError:
                return False
        else:
            try:  # test conversion to int
                if self.get_choice_with_index(int(task_input[self.get_id()])) is None:
                    return False
            except ValueError:
                return False
        return True

    def check_answer(self, task_input, language):
        valid = True
        msgs = []
        invalid_count = 0
        if self._multiple:
            for choice in self._choices:
                if choice["valid"] and not choice["index"] in task_input[self.get_id()] and not str(choice["index"]) in task_input[self.get_id()]:
                    valid = False
                    invalid_count += 1
                elif not choice["valid"] and (choice["index"] in task_input[self.get_id()] or str(choice["index"]) in task_input[self.get_id()]):
                    valid = False
                    invalid_count += 1
            for i in task_input[self.get_id()]:
                feedback = self.get_choice_with_index(int(i))["feedback"]
                if feedback is not None:
                    msgs.append(self.gettext(language, feedback))
        else:
            choice = self.get_choice_with_index(int(task_input[self.get_id()]))
            valid = choice["valid"]
            if not valid:
                invalid_count += 1
            if choice["feedback"] is not None:
                msgs.append(self.gettext(language, choice["feedback"]))

        if not valid:
            if self._error_message is not None:
                msgs = [self.gettext(language, self._error_message)] + msgs
            elif not self._centralize:
                msgs = ["_wrong_answer_multiple" if self._multiple else "_wrong_answer"] + msgs

            if len(msgs) != 0:
                return False, None, msgs, invalid_count
            else:
                return False, None, None, invalid_count

        if self._success_message is not None:
            msgs = [self.gettext(language, self._success_message)] + msgs

        if len(msgs) != 0:
            return True, None, msgs, 0
        else:
            return True, None, None, 0

    @classmethod
    def get_text_fields(cls):
        result = BasicProblem.get_text_fields()
        result.update({"success_message": True, "error_message": True, "choices": [{"text": True, "feedback": True}]})
        return result
