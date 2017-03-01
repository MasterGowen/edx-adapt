"""
This file contains api resources for interacting with the tutor as users take the course.
"""
import time

from flask_restful import abort, reqparse

from edx_adapt.api.resources.base_resource import BaseResource
from edx_adapt.data.interface import DataException
from edx_adapt import logger
from edx_adapt.select.interface import SelectException


class DefaultResource(BaseResource):
    def run_selector(self, course_id, user_id):
        """
        Run the problem selection sequence
        """
        nex = self.repo.get_next_problem(course_id, user_id)

        # only run if no next problem has been selected yet, or there was an error previously
        if nex is None or 'error' in nex:
            logger.info("SELECTOR CHOOSING NEXT PROBLEM")
            prob = self.selector.choose_next_problem(course_id, user_id)
            logger.info("FINISHED CHOOSING NEXT PROBLEM: {}".format(str(prob)))
            self.repo.set_next_problem(course_id, user_id, prob)
        else:
            logger.info("SELECTION NOT REQUIRED!")

    def _rotate_problem(self, next_problem, course_id, user_id, **args):
        if next_problem and 'error' not in next_problem and args['problem'] == next_problem.get('problem_name'):
            self.repo.advance_problem(course_id, user_id)


class UserProblems(DefaultResource):
    """
    Handle request for user's current and next problem.
    """
    def _check_current_done(self, course_id, user_id, current):
        log = self.repo.get_raw_user_data(course_id, user_id)
        done_with_current = any(
            [x for x in log if x['type'] == 'response' and
             x['problem']['problem_name'] == current['problem_name'] and x['correct'] == 1]
        )

        # account for test questions: user is "done" after they input any answer
        if not done_with_current and (current["pretest"] or current["posttest"]):
            done_with_current = any([x for x in log if x['type'] == 'response'])
        return done_with_current

    def _check_course_done(self, course_id, user_id):
        fin = self.repo.get_finished_users(course_id)
        done_with_course = user_id in fin
        if not done_with_course:
            answers = self.repo.get_all_interactions(course_id, user_id)
            done_with_course = (
                # Course set to be done if student answer correctly on more than a half of pre-assessment problems
                sum([x['correct'] for x in answers if (x['problem']['pretest'])]) > (
                    self.repo.get_num_pretest(course_id) // 2
                )
            )
        return done_with_course

    def get(self, course_id, user_id):
        try:
            nex = self.repo.get_next_problem(course_id, user_id)
            cur = self.repo.get_current_problem(course_id, user_id)
        except DataException as e:
            abort(404, message=e.message)

        okay = bool(nex and 'error' not in nex)

        done_with_course = False
        if not cur:
            done_with_current = True
        else:
            try:
                done_with_current = self._check_current_done(course_id, user_id, cur)
                done_with_course = self._check_course_done(course_id, user_id)
            except DataException as e:
                logger.exception("DATA EXCEPTION: ")
                abort(500, message=str(e))
        return {
            "next": nex, "current": cur, "done_with_current": done_with_current, "okay": okay,
            "done_with_course": done_with_course
        }


# Argument parser for posting a user response
result_parser = reqparse.RequestParser()
result_parser.add_argument('problem', type=str, required=True, location='json',
                           help="Must supply the name of the problem which the user answered")
result_parser.add_argument('correct', type=int, required=True, location='json',
                           help="Must supply correctness, 0 for incorrect, 1 for correct")
result_parser.add_argument('attempt', type=int, required=True, location='json',
                           help="Must supply the attempt number, starting from 1 for the first attempt")
result_parser.add_argument('unix_seconds', type=int, location='json',
                           help="Optionally supply timestamp in seconds since unix epoch")


class UserInteraction(DefaultResource):
    """
    Post a user's response to their current problem.
    """
    def post(self, course_id, user_id):
        args = result_parser.parse_args()
        timestamp = args['unix_seconds'] or int(time.time())

        try:
            # If this is a response to the "next" problem, advance to it first before storing
            # (shouldn't happen if PageLoad messages are posted correctly, but we won't require that)
            nex = self.repo.get_next_problem(course_id, user_id)
            self._rotate_problem(nex, course_id, user_id, **args)
            self.repo.post_interaction(course_id, args['problem'], user_id, args['correct'], args['attempt'], timestamp)

            # the user needs a new problem, start choosing one
            self.run_selector(course_id, user_id)
        except SelectException as e:
            abort(500, message="Interaction successfully stored, but an error occurred starting "
                               "a problem selection: " + e.message)
        except DataException as e:
            logger.exception("DATA EXCEPTION:")
            abort(500, message=e.message)

        return {"success": True}, 201

load_parser = reqparse.RequestParser()
load_parser.add_argument('problem', required=True, help="Must supply the name of the problem loaded", location='json')
load_parser.add_argument('unix_seconds', type=int, help="Optionally supply timestamp in seconds since unix epoch",
                         location='json')


class UserPageLoad(DefaultResource):
    """
    Post the time when a user loads a problem. Used to log time spent solving a problem.
    """
    def post(self, course_id, user_id):
        args = load_parser.parse_args()
        timestamp = args['unix_seconds'] or int(time.time())

        try:
            self.repo.post_load(course_id, args['problem'], user_id, timestamp)
            nex = self.repo.get_next_problem(course_id, user_id)
            self._rotate_problem(nex, course_id, user_id, **args)
        except DataException as e:
            logger.exception("DATA EXCEPTION:")
            abort(500, message=e.message)

        return {"success": True}, 201
