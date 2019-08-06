# -*- coding: utf-8 -*-
#
# This file is part of INGInious. See the LICENSE and the COPYRIGHTS files for
# more information about the licensing of this file.

""" Index page """
from collections import OrderedDict
from inginious.frontend.pages.utils import INGIniousPage

from inginious.frontend.courses import WebAppCourse


class CourseListPage(INGIniousPage):
    """ Index page """

    def GET(self):  # pylint: disable=arguments-differ
        """ Display main course list page """
        return self.show_page()

    def POST(self):  # pylint: disable=arguments-differ
        """ Display main course list page """
        return self.show_page()

    def show_page(self):
        """  Display main course list page """
        username = self.user_manager.session_username()
        user_info = self.database.users.find_one({"username": username})
        all_courses = {course["_id"]: WebAppCourse(course["_id"], course, self.task_factory, self.plugin_manager) for course in self.database.courses.find()}

        # Display
        open_courses = {courseid: course for courseid, course in all_courses.items() if course.is_open_to_non_staff()}
        open_courses = OrderedDict(sorted(iter(open_courses.items()), key=lambda x: x[1].get_name(self.user_manager.session_language())))

        return self.template_helper.get_renderer().index(open_courses, user_info)
