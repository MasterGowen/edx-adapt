""" This file contains api resources for interacting with the tutor
as users take the course.
"""

import threading
import time

from flask_restful import Resource, abort, reqparse

from edx_adapt.data.interface import DataException
from edx_adapt.select.interface import SelectException

from edx_adapt.misc import psiturk_with_bo

""" Handle request for user's current and next problem """
class UserProblems(Resource):
    # Name of the question to test whether the user is paying attention on pretest.
    ATTENTION_QUESTION_NAME = 'Pre_assessment_13'

    def __init__(self, **kwargs):
        self.repo = kwargs['data']
        """@type repo: DataInterface"""

    def get(self, course_id, user_id):
        nex = {}
        cur = {}
        try:
            nex = self.repo.get_next_problem(course_id, user_id)
            cur = self.repo.get_current_problem(course_id, user_id)
        except DataException as e:
            abort(404, message=e.message)

        okay = True
        if not nex or 'error' in nex:
            okay = False

        done_with_current = False
        done_with_course = False

        if not cur:
            done_with_current = True
        else:
            try:
                log = self.repo.get_raw_user_data(course_id, user_id)
                current_correct = [x for x in log if x['type'] == 'response' and
                                   x['problem']['problem_name'] == cur['problem_name'] and x['correct'] == 1]
                done_with_current = ( len(current_correct) > 0)

                #account for test questions: user is "done" after they input any answer
                if cur["pretest"] or cur["posttest"]:
                    if len([x for x in log if x['type'] == 'response']) > 0:
                        done_with_current = True

                fin = self.repo.get_finished_users(course_id)
                if user_id in fin:
                    done_with_course = True
                #reject high pretest scores
                # if more than 7 out of the first 13 pretest questions are correct -
                # then the user knows too much already (ATTENTION_QUESTION_NAME
                # is only for checking that the user is paying attention,
                # not knowledge assessment, so skip it)
                answers = self.repo.get_all_interactions(course_id, user_id)
                if sum( [x['correct'] for x in answers if (x['problem']['pretest'] and x['problem']['problem_name'] != UserProblems.ATTENTION_QUESTION_NAME) ] ) > 7:
                    done_with_course = True
                    nex = None
                # if answer to ATTENTION_QUESTION_NAME is wrong -
                # then filter out this user, because they are not paying
                # attention and simply clicking buttons
                pretest_done = len(self.repo.get_all_remaining_pretest_problems(course_id, user_id)) == 0
                # Disable cut off of students who gave no correct answers at pre-assessment for easier debugging
                # if pretest_done and (sum( [x['correct'] for x in answers if (x['problem']['pretest'] and x['problem']['problem_name'] == UserProblems.ATTENTION_QUESTION_NAME) ] ) < 1):
                if pretest_done and (sum( [x['correct'] for x in answers if (x['problem']['pretest'] and x['problem']['problem_name'] == UserProblems.ATTENTION_QUESTION_NAME) ] ) < 0):
                    done_with_course = True
                    nex = None


            except DataException as e:
                print("--------------------\tDATA EXCEPTION: " + str(e))
                abort(500, message=str(e))

        return {"next": nex, "current": cur, "done_with_current": done_with_current, "okay": okay, "done_with_course": done_with_course}


""" Argument parser for posting a user response """
result_parser = reqparse.RequestParser()
result_parser.add_argument('problem', type=str, required=True, location='json',
                           help="Must supply the name of the problem which the user answered")
result_parser.add_argument('correct', type=int, required=True, location='json',
                           help="Must supply correctness, 0 for incorrect, 1 for correct")
result_parser.add_argument('attempt', type=int, required=True, location='json',
                           help="Must supply the attempt number, starting from 1 for the first attempt")
result_parser.add_argument('unix_seconds', type=int, location='json',
                           help="Optionally supply timestamp in seconds since unix epoch")
"""result_parser.add_argument('done', type=bool, required=True,
                           help="Legacy support for multiple part problems. Supply false if"
                                " the user must answer more parts, otherwise leave this true")"""

""" Global lock for calling choose_next_problem """
selector_lock = threading.Lock()

""" Run the problem selection sequence (in separate thread) """
def run_selector(course_id, user_id, selector, repo):
    with selector_lock:
        """@type selector: SelectInterface"""
        """@type repo: DataInterface"""
        print("--------------------\tSELECTOR LOCK ACQUIRED!")
        nex = None
        try:
            nex = repo.get_next_problem(course_id, user_id)
        except DataException as e:
            # exception here probably means the user/course combo doesn't exist. Screw it, quit
            return

        # only run if no next problem has been selected yet, or there was an error previously
        if nex is None or 'error' in nex:
            try:
                print("--------------------\tSELECTOR CHOOSING NEXT PROBLEM")
                prob = selector.choose_next_problem(course_id, user_id)
                print("--------------------\tFINISHED CHOOSING NEXT PROBLEM: ")
                print("--------------------\t" + str(prob))
                repo.set_next_problem(course_id, user_id, prob)
            except SelectException as e:
                # assume that the user/course exists. Set an error...
                print("--------------------\tSELECTION EXCEPTION OCCURED: " + str(e))
                repo.set_next_problem(course_id, user_id, {'error': str(e)})

            except DataException as e:
                print("--------------------\tDATA EXCEPTION HAPPENED, OH NO!" + str(e))
                #TODO: after deciding if set_next_problem could throw an exception here

        else:
            print("--------------------\tSELECTION NOT REQUIRED!")


""" Post a user's response to their current problem """
class UserInteraction(Resource):
    def __init__(self, **kwargs):
        self.repo = kwargs['data']
        self.selector = kwargs['selector']
        """@type repo: DataInterface"""
        """@type selector: SelectInterface"""

    def post(self, course_id, user_id):
        args = result_parser.parse_args()
        if args['unix_seconds'] is None:
            args['unix_seconds'] = int(time.time())

        try:
            # If this is a response to the "next" problem, advance to it first before storing
            # (shouldn't happen if PageLoad messages are posted correctly, but we won't require that)
            nex = self.repo.get_next_problem(course_id, user_id)
            if nex and 'error' not in nex and args['problem'] == nex['problem_name']:
                self.repo.advance_problem(course_id, user_id)

            #TODO: guard against answering other problems...?
            #possibly outside the scope of this software

            self.repo.post_interaction(course_id, args['problem'], user_id, args['correct'],
                                       args['attempt'], args['unix_seconds'])

            #is the user now done? if so hack in a call to psiturk+bo module TODO: do this only once
            """
            if user_id in self.repo.get_finished_users(course_id):
                print "USER IS DONE! ONTO BAYESIAN OPTIMIZATION!"
                psiturk_with_bo.set_next_users_parameters(self.repo, self.selector, course_id)
            """

            # the user needs a new problem, start choosing one
            try:
                print("--------------------\tSTARTING SELECTOR!")
                """t = threading.Thread(target=run_selector, args=(course_id, user_id, self.selector, self.repo))
                t.start()
                t.join()
                #TODO: actually run in other thread """
                run_selector(course_id, user_id, self.selector, self.repo)
            except Exception as e:
                print("--------------------\tEXCEPTION STARTING SELECTION THREAD: " + str(e))
                abort(500, message="Interaction successfully stored, but an error occurred starting "
                                   "a problem selection thread: " + e.message)

        except DataException as e:
            print("--------------------\tDATA EXCEPTION: " + str(e))
            abort(500, message=e.message)

        return {"success": True}, 200

load_parser = reqparse.RequestParser()
load_parser.add_argument('problem', required=True, help="Must supply the name of the problem loaded", location='json')
load_parser.add_argument('unix_seconds', type=int, help="Optionally supply timestamp in seconds since unix epoch",
                         location='json')

""" Post the time when a user loads a problem. Used to log time spent solving a problem """
class UserPageLoad(Resource):
    def __init__(self, **kwargs):
        self.repo = kwargs['data']
        """@type repo: DataInterface"""

    def post(self, course_id, user_id):
        args = load_parser.parse_args()
        if args['unix_seconds'] is None:
            args['unix_seconds'] = int(time.time())

        try:
            self.repo.post_load(course_id, args['problem'], user_id, args['unix_seconds'])
            nex = self.repo.get_next_problem(course_id, user_id)
            if nex and 'error' not in nex and args['problem'] == nex['problem_name']:
                self.repo.advance_problem(course_id, user_id)
        except DataException as e:
            print("--------------------\tDATA EXCEPTION: " + str(e))
            abort(500, message=e.message)

        return {"success": True}, 200
