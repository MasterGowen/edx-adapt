"""
This file contains api resources for serving data from the course.
"""

from flask_restful import abort

from edx_adapt.api.resources.base_resource import BaseResource
from edx_adapt.data.interface import DataException
from edx_adapt import logger


class SingleProblemRequest(BaseResource):
    """
    Handle request for a user's log on one problem
    """

    def get(self, course_id, user_id, problem_name):
        problog = []
        try:
            log = self.repo.get_raw_user_data(course_id, user_id)
            problog = [x for x in log if x['problem']['problem_name'] == problem_name]
        except DataException as e:
            logger.error("Data exception: {}".format(e))
            abort(500, message=str(e))
        return {'log': problog}


class UserLogRequest(BaseResource):
    """
    Handle request for a user's log
    """
    def get(self, course_id, user_id):
        log = []
        try:
            log = self.repo.get_raw_user_data(course_id, user_id)
        except DataException as e:
            logger.error("Data exception: {}".format(e))
            abort(500, message=str(e))
        return {'log': log}


class CourseLogRequest(BaseResource):
    """
    Handle request for logs from all users of a course
    """
    def get(self, course_id):
        data = {}
        try:
            users = self.repo.get_in_progress_users(course_id)
            users.extend(self.repo.get_finished_users(course_id))

            for user in users:
                data[user] = self.repo.get_raw_user_data(course_id, user)

        except DataException as e:
            logger.error("Data exception: {}".format(e))
            abort(500, message=str(e))
        return {'log': data}


class ExperimentLogRequest(BaseResource):
    """
    Handle request for logs from all users from an experiment (only gives logs for finished users)
    """
    def get(self, course_id, experiment_name):
        data = {}
        try:
            users = self.repo.get_subjects(course_id, experiment_name)

            for user in users:
                data[user] = self.repo.get_raw_user_data(course_id, user)

        except DataException as e:
            logger.error("Data exception: {}".format(e))
            abort(500, message=str(e))
        return {'log': data}


def _fulfill_correct(repo, course_id, user_id):
    correct = {}
    correct['pretest'] = [x['correct'] for x in repo.get_all_interactions(course_id, user_id)
                          if x['problem']['pretest']]
    correct['posttest'] = [x['correct'] for x in repo.get_all_interactions(course_id, user_id)
                           if x['problem']['posttest']]
    correct['problems'] = [x['correct'] for x in repo.get_all_interactions(course_id, user_id)
                           if not (x['problem']['posttest'] and x['problem']['pretest'])]
    return correct


def _fulfill_skills(repo, course_id, user_id):
    skills = {}
    skills['pretest'] = [x['problem']['skills'][0] for x in repo.get_all_interactions(course_id, user_id)
                         if x['problem']['pretest']]
    skills['posttest'] = [x['problem']['skills'][0] for x in repo.get_all_interactions(course_id, user_id)
                          if x['problem']['posttest']]
    skills['problems'] = [x['problem']['skills'][0] for x in repo.get_all_interactions(course_id, user_id)
                          if x['problem']['posttest'] is False and x['problem']['pretest'] is False]
    return skills


# helper function
def fill_user_data(repo, course_id, user_id):
    data = {}
    correct = {}
    num_pre = {}
    num_post = {}

    data['all'] = repo.get_all_interactions(course_id, user_id)
    correct['all'] = repo.get_whole_trajectory(course_id, user_id)

    correct.update(_fulfill_correct(repo, course_id, user_id))

    data['by_skill'] = {}
    correct['by_skill'] = {}

    for skill in repo.get_skills(course_id):
        data['by_skill'][skill] = repo.get_interactions(course_id, skill, user_id)
        correct['by_skill'][skill] = repo.get_skill_trajectory(course_id, skill, user_id)
        num_pre[skill] = repo.get_num_pretest(course_id, skill)
        num_post[skill] = repo.get_num_posttest(course_id, skill)

    skills = _fulfill_skills(repo, course_id, user_id)

    blob = {
        'data': data,
        'trajectories': correct,
        'trajectory_skills': skills,
        'pretest_length': num_pre,
        'posttest_length': num_post
    }
    return blob


class UserTrajectoryRequest(BaseResource):
    """
    Handle request for a user's trajectories
    """
    def get(self, course_id, user_id):
        blob = {'data': {}, 'trajectories': {}, 'pretest_length': {}, 'posttest_length': {}}
        try:
            blob = fill_user_data(self.repo, course_id, user_id)

        except DataException as e:
            logger.exception("Data exception:")
            abort(500, message=str(e))
        return blob


class CourseTrajectoryRequest(BaseResource):
    """
    Handle request for logs from all users of a course
    """
    def get(self, course_id):
        userblobs = {}
        try:
            users = self.repo.get_in_progress_users(course_id)
            users.extend(self.repo.get_finished_users(course_id))

            for user in users:
                blob = fill_user_data(self.repo, course_id, user)
                userblobs[user] = blob

        except DataException as e:
            logger.error("Data exception: {}".format(e))
            abort(500, message=str(e))
        return userblobs


class ExperimentTrajectoryRequest(BaseResource):
    """
    Handle request for logs from all users from an experiment (only gives logs for finished users)
    """
    def get(self, course_id, experiment_name):
        userblobs = {}
        try:
            users = self.repo.get_subjects(course_id, experiment_name)

            for user in users:
                blob = fill_user_data(self.repo, course_id, user)
                userblobs[user] = blob

        except DataException as e:
            logger.error("Data exception: {}".format(e))
            abort(500, message=str(e))
        return userblobs
