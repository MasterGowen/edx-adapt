""" This file contains api resources for setting model parameters for a course
"""
import random

from flask_restful import Resource, abort, reqparse

from edx_adapt.data.interface import DataException
from edx_adapt import logger
from edx_adapt.select.interface import SelectException

param_parser = reqparse.RequestParser()
param_parser.add_argument('course_id', type=str, location='json', help="Optionally supply a course id")
param_parser.add_argument('user_id', type=str, location='json', help="Optionally supply a user ID")
param_parser.add_argument('skill_name', type=str, location='json', help="Optionally supply the name of a skill")
param_parser.add_argument('params', type=dict, location='json', required=True,
                          help="Please supply the desired model parameters as a dictionary")


class Parameters(Resource):
    def __init__(self, **kwargs):
        """
        @type repo: DataInterface
        @type selector: SelectInterface
        """
        self.repo = kwargs['data']
        self.selector = kwargs['selector']

    def get(self):
        param_list = []
        try:
            param_list = self.selector.get_all_parameters()
        except SelectException as e:
            abort(500, message=str(e))
        return {'parameters': param_list}, 200

    def post(self):
        args = param_parser.parse_args()
        course = args['course_id']
        user = args['user_id']
        skill = args['skill_name']
        params = args['params']

        prob_list = self.repo.get_model_params(course)
        if prob_list:
            params = random.choice(prob_list)
        try:
            self.selector.set_parameter(params, course, user, skill)
        except SelectException as e:
            abort(500, message=str(e))

        return {'success': True}, 200

param_bulk_parser = reqparse.RequestParser()
param_bulk_parser.add_argument('course_id', type=str, location='json', help="Optionally supply a course id")
param_bulk_parser.add_argument('user_id', type=str, location='json', help="Optionally supply a user ID")
param_bulk_parser.add_argument(
    'skills_list', type=list, location='json', help="Optionally supply the list with skill names"
)
param_bulk_parser.add_argument(
    'params',
    type=dict,
    location='json',
    required=True,
    help="Please supply the desired model parameters as a dictionary")


class ParametersBulk(Resource):
    def __init__(self, **kwargs):
        self.repo = kwargs['data']
        self.selector = kwargs['selector']

    def get(self):
        param_list = []
        try:
            param_list = self.selector.get_all_parameters()
        except SelectException as e:
            abort(500, message=str(e))
        return {'parameters': param_list}, 200

    def post(self):
        args = param_parser.parse_args()
        course = args['course_id']
        user = args['user_id']
        try:
            skills_list = self.repo.get_skills(course)

            prob_list = self.repo.get_model_params(course)
        except DataException:
            logger.exception(
                "Skills field are not found in the course: {}, student's skills cannot be added".format(course)
            )
            abort(
                500,
                "Course doesn't contain skills, please update the course {} and try adding student again.".format(
                    course
                )
            )
        logger.info(
            "Skills for the student {} are taken directly from the course {} in which student is enrolled".format(
                user, course
            )
        )
        params = random.choice(prob_list) if prob_list else args['params']
        try:
            for skill in skills_list:
                self.selector.set_parameter(params, course, user, skill)
        except SelectException as e:
            abort(500, message=str(e))
        return {'success': True, 'configuredSkills': skills_list}, 201
