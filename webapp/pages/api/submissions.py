# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2015 Université Catholique de Louvain.
#
# This file is part of INGInious.
#
# INGInious is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# INGInious is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with INGInious.  If not, see <http://www.gnu.org/licenses/>.
""" Submissions """

import web

from webapp.pages.api._api_page import APIAuthenticatedPage, APINotFound, APIForbidden, APIInvalidArguments
from common.tasks_code_boxes import FileBox
from common.tasks_problems import MultipleChoiceProblem, BasicCodeProblem

def _get_submissions(course_factory, submission_manager, user_manager, courseid, taskid, submissionid=None):
    """
        Helper for the GET methods of the two following classes
    """

    try:
        course = course_factory.get_course(courseid)
    except:
        raise APINotFound("Course not found")

    if not user_manager.course_is_open_to_user(course):
        raise APIForbidden("You are not registered to this course")

    try:
        task = course.get_task(taskid)
    except:
        raise APINotFound("Task not found")

    if submissionid is None:
        submissions = submission_manager.get_user_submissions(task)
    else:
        try:
            submissions = [submission_manager.get_submission(submissionid)]
        except:
            raise APINotFound("Submission not found")
        if submissions[0]["taskid"] != task.get_id() or submissions[0]["courseid"] != course.get_id():
            raise APINotFound("Submission not found")

    output = []

    for submission in submissions:
        data = {
            "id": str(submission["_id"]),
            "submitted_on": str(submission["submitted_on"]),
            "status": submission["status"],
            "input": submission_manager.get_input_from_submission(submission, True),
            "grade": submission["grade"]
        }
        if submission["status"] == "done":
            data["result"] = submission.get("result", "crash")
            data["feedback"] = submission.get("text", "")
            data["problems_feedback"] = submission.get("problems", {})

        output.append(data)

    return 200, output


class APISubmissionSingle(APIAuthenticatedPage):
    """
        Endpoint /api/v0/courses/[a-zA-Z_\-\.0-9]+/tasks/[a-zA-Z_\-\.0-9]+/submissions/[a-zA-Z_\-\.0-9]+
    """

    def API_GET(self, courseid, taskid, submissionid):
        """
            List all the submissions that the connected user made. Returns dicts in the form

            ::

                {
                    "submission_id1":
                    {
                        "submitted_on": "date",
                        "status" : "done",          #can be "done", "waiting", "error" (execution status of the task).
                        "grade": 0.0,
                        "input": {},                #the input data. File are base64 encoded.
                        "result" : "success"        #only if status=done. Result of the execution.
                        "feedback": ""              #only if status=done. the HTML global feedback for the task
                        "problems_feedback":        #only if status=done. HTML feedback per problem. Some pid may be absent.
                        {
                            "pid1": "feedback1",
                            #...
                        }
                    }
                    #...
                }

            If you use the endpoint /api/v0/courses/the_course_id/tasks/the_task_id/submissions/submissionid,
            this dict will contain one entry or the page will return 404 Not Found.
        """
        return _get_submissions(self.course_factory, self.submission_manager, self.user_manager, courseid, taskid, submissionid)


class APISubmissions(APIAuthenticatedPage):
    """
        Endpoint /api/v0/courses/[a-zA-Z_\-\.0-9]+/tasks/[a-zA-Z_\-\.0-9]+/submissions
    """

    def API_GET(self, courseid, taskid):
        """
            List all the submissions that the connected user made. Returns dicts in the form

            ::

                {
                    "submission_id1":
                    {
                        "submitted_on": "date",
                        "status" : "done",          #can be "done", "waiting", "error" (execution status of the task).
                        "grade": 0.0,
                        "input": {},                #the input data. File are base64 encoded.
                        "result" : "success"        #only if status=done. Result of the execution.
                        "feedback": ""              #only if status=done. the HTML global feedback for the task
                        "problems_feedback":        #only if status=done. HTML feedback per problem. Some pid may be absent.
                        {
                            "pid1": "feedback1",
                            #...
                        }
                    }
                    #...
                }

            If you use the endpoint /api/v0/courses/the_course_id/tasks/the_task_id/submissions/submissionid,
            this dict will contain one entry or the page will return 404 Not Found.
        """
        return _get_submissions(self.course_factory, self.submission_manager, self.user_manager, courseid, taskid)

    def API_POST(self, courseid, taskid):
        """
            Creates a new submissions. Takes as (POST) input the key of the subproblems, with the value assigned each time.

            Returns

            - an error 400 Bad Request if all the input is not (correctly) given,
            - an error 403 Forbidden if you are not allowed to create a new submission for this task
            - an error 404 Not found if the course/task id not found
            - an error 500 Internal server error if the grader is not available,
            - 200 Ok, with {"submissionid": "the submission id"} as output.
        """

        try:
            course = self.course_factory.get_course(courseid)
        except:
            raise APINotFound("Course not found")

        username = self.user_manager.session_username()

        if not self.user_manager.course_is_open_to_user(course, username):
            raise APIForbidden("You are not registered to this course")

        try:
            task = course.get_task(taskid)
        except:
            raise APINotFound("Task not found")

        self.user_manager.user_saw_task(username, courseid, taskid)

        # Verify rights
        if not self.user_manager.task_can_user_submit(task, username):
            raise APIForbidden("Deadline reached")

        init_var = self.list_multiple_multiple_choices_and_files(task)
        user_input = task.adapt_input_for_backend(web.input(**init_var))

        if not task.input_is_consistent(user_input, self.default_allowed_file_extensions, self.default_max_file_size):
            raise APIInvalidArguments()

        # Get debug info if the current user is an admin
        debug = self.user_manager.has_admin_rights_on_course(course, username)

        # Start the submission
        submissionid = self.submission_manager.add_job(task, user_input, debug)

        return 200, {"submissionid": str(submissionid)}

    def list_multiple_multiple_choices_and_files(self, task):
        """ List problems in task that expect and array as input """
        output = {}
        for problem in task.get_problems():
            if isinstance(problem, MultipleChoiceProblem) and problem.allow_multiple():
                output[problem.get_id()] = []
            elif isinstance(problem, BasicCodeProblem):
                for box in problem.get_boxes():
                    if isinstance(box, FileBox):
                        output[box.get_complete_id()] = {}
        return output
