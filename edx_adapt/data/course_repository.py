"""Repository that implements DataInterface using a tinydb backend """

from datetime import datetime

import interface
import random

from edx_adapt import logger


class CourseRepository(interface.DataInterface):
    """
    Implementation of the DataInterface.
    """

    def __init__(self, storage_module):
        super(CourseRepository, self).__init__(storage_module)
        """@type self.store: StorageInterface"""
        self.generic_table_name = "Generic"
        try:
            self.store.create_table(self.generic_table_name, [['key', 'ascending']])
            self.store.set(self.generic_table_name, "MAGIC JOHNSON", "This is the generic store table")
        except interface.DataException as e:
            logger.exception("(Generic table already existing is okay) Make sure this isn't a problem:")
            pass

    """ Course setup methods """
    def post_course(self, course_id, *args):
        self.store.create_table(course_id)
        self.store.set(course_id, 'users_in_progress', [])
        self.store.set(course_id, 'users_finished', [])
        self.store.set(course_id, 'skills', [])
        self.store.set(course_id, 'problems', [])
        self.store.set(course_id, 'experiments', [])

    def post_skill(self, course_id, skill_name):
        self.store.append(course_id, 'skills', skill_name)

    def _add_problem(self, course_id, skill_names, problem_name, tutor_url, b_pretest, b_posttest):
        skills = self.store.get(course_id, 'skills')
        for skill in skill_names:
            if skill not in skills:
                raise interface.DataException("No such skill: {}".format(skill))
        self.store.append(course_id, 'problems', {'problem_name': problem_name, 'tutor_url': tutor_url,
                                            'pretest': b_pretest, 'posttest': b_posttest, 'skills':skill_names})

    def post_problem(self, course_id, skill_names, problem_name, tutor_url):
        self._add_problem(course_id, skill_names, problem_name, tutor_url, False, False)

    def post_pretest_problem(self, course_id, skill_names, problem_name, tutor_url):
        self._add_problem(course_id, skill_names, problem_name, tutor_url, True, False)

    def post_posttest_problem(self, course_id, skill_names, problem_name, tutor_url):
        self._add_problem(course_id, skill_names, problem_name, tutor_url, False, True)

    def enroll_user(self, course_id, user_id):
        self.store.append(course_id, 'users_in_progress', user_id)
        self.store.set(course_id, self._get_user_log_key(user_id), [])
        self.store.set(course_id, self._get_user_problem_key(user_id), {'current': None, 'next': None})

    """ Retrieve course information """
    def get_course_ids(self):
        courses = self.store.get_tables()
        courses.remove(self.generic_table_name)
        return list(courses)

    def get_skills(self, course_id):
        skills = self.store.get(course_id, 'skills')
        #if 'None' in skills:
        #    skills.remove('None')
        return skills

    def get_problems(self, course_id, skill_name=None):
        """ Get all problems related to this course-skill pair:, pretest, normal, and posttest """
        problems = self.store.get(course_id, 'problems')
        if skill_name == None:
            return problems
        else:
            return [x for x in problems if skill_name in x['skills']]

    def get_num_pretest(self, course_id, skill_name):
        pretest = [x for x in self.get_problems(course_id, skill_name) if x['pretest'] == True]
        return len(pretest)

    def get_num_posttest(self, course_id, skill_name):
        posttest = [x for x in self.get_problems(course_id, skill_name) if x['posttest'] == True]
        return len(posttest)

    def get_in_progress_users(self, course_id):
        return self.store.get(course_id, 'users_in_progress')

    def get_finished_users(self, course_id):
        return self.store.get(course_id, 'users_finished')

    """ Add user data """
    def post_interaction(self, course_id, problem_name, user_id, correct, attempt, unix_seconds):
        problem = self._get_problem(course_id, problem_name)
        key = self._get_user_log_key(user_id)
        data = {'problem': problem, 'correct': correct, 'attempt': attempt, 'unix_s': unix_seconds, 'type': 'response',
                'timestamp': datetime.fromtimestamp(unix_seconds).strftime('%Y-%m-%d %H:%M:%S')}

        old_attempt = [
            x for x in self.get_raw_user_data(course_id, user_id) if x['problem']['problem_name'] == problem_name and
            x['type'] == 'response' and x['attempt'] == attempt
        ]

        if len(old_attempt) > 0:
            # don't record the same attempt twice
            return

        # allow the exception from append to throw if some shit goes down
        self.store.append(course_id, key, data)

        # is user finished...?
        remaining_post = self.get_all_remaining_posttest_problems(course_id, user_id)
        if len(remaining_post) == 0:
            if user_id in self.get_in_progress_users(course_id):
                self.store.append(course_id, 'users_finished', user_id)
                prog = self.store.get(course_id, 'users_in_progress')
                prog.remove(user_id)
                self.store.set(course_id, 'users_in_progress', prog)

    def post_load(self, course_id, problem_name, user_id, unix_seconds):
        problem = self._get_problem(course_id, problem_name)
        if (
            problem != self.get_current_problem(course_id, user_id) and
            problem != self.get_next_problem(course_id, user_id)
        ):
            # Don't log if this isn't the right problem
            return

        key = self._get_user_log_key(user_id)
        data = {'problem': problem, 'unix_s': unix_seconds, 'type': 'page_load',
                'timestamp': datetime.fromtimestamp(unix_seconds).strftime('%Y-%m-%d %H:%M:%S')}

        older_loads = [x for x in self.get_raw_user_data(course_id, user_id)
                       if x['problem']['problem_name'] == problem_name and x['type'] == 'page_load']
        if len(older_loads) > 0:
            # already stored a load time for this problem. For now, don't record this one
            return

        self.store.append(course_id, key, data)

    def set_next_problem(self, course_id, user_id, problem_dict):
        # if no error, assert that this problem exists in this course:
        if 'error' not in problem_dict:
            problem_dict = self._get_and_assert_problem_exists(course_id, problem_dict)

        curnext = self.store.get(course_id, self._get_user_problem_key(user_id))
        curnext['next'] = problem_dict

        self.store.set(course_id, self._get_user_problem_key(user_id), curnext)

    def advance_problem(self, course_id, user_id):
        """
        required: Must set user's next problem to 'None'
        """
        curnext = self.store.get(course_id, self._get_user_problem_key(user_id))
        # assert that next problem is valid (it could be an error message)
        next_problem = self._get_and_assert_problem_exists(course_id, curnext['next'])
        curnext['current'] = next_problem
        curnext['next'] = None
        self.store.set(course_id, self._get_user_problem_key(user_id), curnext)

    """ Retrieve user information """
    def get_all_remaining_problems(self, course_id, user_id):
        return [x for x in self._get_remaining_by_user(course_id, user_id)
                if x['pretest'] == False and x['posttest'] == False]

    def get_remaining_problems(self, course_id, skill_name, user_id):
        remaining = self.get_all_remaining_problems(course_id, user_id)
        return [x for x in remaining if skill_name in x['skills']]

    def get_all_remaining_posttest_problems(self, course_id, user_id):
        return [x for x in self._get_remaining_by_user(course_id, user_id) if x['posttest'] == True]

    def get_remaining_posttest_problems(self, course_id, skill_name, user_id):
        remaining = self.get_all_remaining_posttest_problems(course_id, user_id)
        return [x for x in remaining if skill_name in x['skills']]

    def get_all_remaining_pretest_problems(self, course_id, user_id):
        return [x for x in self._get_remaining_by_user(course_id, user_id) if x['pretest'] == True]

    def get_remaining_pretest_problems(self, course_id, skill_name, user_id):
        remaining = self.get_all_remaining_pretest_problems(course_id, user_id)
        return [x for x in remaining if skill_name in x['skills']]

    def get_whole_trajectory(self, course_id, user_id):
        return [x['correct'] for x in self.get_all_interactions(course_id, user_id)]

    def get_skill_trajectory(self, course_id, skill_name, user_id):
        return [x['correct'] for x in self.get_interactions(course_id, skill_name, user_id)]

    def get_all_interactions(self, course_id, user_id):
        return[{'problem': x['problem'], 'correct': x['correct'], 'unix_s': x['unix_s']}
               for x in self.get_raw_user_data(course_id, user_id) if x['type'] == 'response' and x['attempt'] == 1]

    def get_interactions(self, course_id, skill_name, user_id):
        return[{'problem': x['problem'], 'correct': x['correct'], 'unix_s': x['unix_s']}
               for x in self.get_raw_user_skill_data(course_id, skill_name, user_id)
               if x['type'] == 'response' and x['attempt'] == 1]

    def get_current_problem(self, course_id, user_id):
        return self.store.get(course_id, self._get_user_problem_key(user_id))['current']

    def get_next_problem(self, course_id, user_id):
        return self.store.get(course_id, self._get_user_problem_key(user_id))['next']

    def get_raw_user_data(self, course_id, user_id):
        return self.store.get(course_id, self._get_user_log_key(user_id))

    def get_raw_user_skill_data(self, course_id, skill_name, user_id):
        return [x for x in self.get_raw_user_data(course_id, user_id) if skill_name in x['problem']['skills']]


    """ Methods to group users by experiment, e.g. for AB policy testing """
    def post_experiment(self, course_id, experiment_name, start, end):
        experiment = {'experiment_name': experiment_name, 'start_time': start, 'end_time': end}
        self.store.append(course_id, 'experiments', experiment)

    def get_experiments(self, course_id):
        return self.store.get(course_id, 'experiments')

    def get_experiment(self, course_id, experiment_name):
        expl = [x for x in self.get_experiments(course_id) if x['experiment_name'] == experiment_name]
        if len(expl) == 0:
            raise interface.DataException("Experiment not found: {}".format(experiment_name))
        return expl[0]

    def get_subjects(self, course_id, experiment_name):
        # return finished users who answered posttest questions within the time frame
        exp = self.get_experiment(course_id, experiment_name)
        users = self.get_finished_users(course_id)
        # not gonna try to put this all in one list comprehension...
        subjects = []
        for user in users:
            data = self.get_raw_user_data(course_id, user)
            for d in data:
                if d['problem']['posttest'] and d['unix_s'] > exp['start_time'] and d['unix_s'] < exp['end_time']:
                    subjects.append(user)
                    break
        return subjects

    def delete_experiment(self, course_id, experiment_name):
        exp = self.get_experiment(course_id, experiment_name)
        l = self.store.get(course_id, 'experiments')
        l.remove(exp)
        self.store.set(course_id, 'experiments', l)

    """ General backing store access: allows other modules
    access to persistent storage
    """
    def set(self, key, value):
        logger.info("GENERIC DB_SET GOING DOWN!")
        logger.info("KEY: {}".format(str(key)))
        logger.info("VAL: {}".format(str(value)))
        self.store.set(self.generic_table_name, key, value)
        logger.info("GENERIC DB_SET DONE!")

    def get(self, key):
        logger.info("GENERIC DB_GET GRABBING: {}".format(str(key)))
        return self.store.get(self.generic_table_name, key)

    def _get_user_log_key(self, user_id):
        return user_id + "_log"

    def _get_user_problem_key(self, user_id):
        return user_id + "_cur_next"

    def _get_problem(self, course_id, problem_name, problem_d=None):
        problems = self.store.get(course_id, 'problems')
        problem = [x for x in problems if x['problem_name'] == problem_name]
        if len(problem) == 0:
            raise interface.DataException("Problem not found: {}".format(problem_name))

        random.shuffle(problem) #hack because joe is tired. shouldn't be multiple problems here anyway
        logger.info(problem)

        pret = problem[0]
        if problem_d is not None:
            #the whole problem was actually specified. Check for a match
            for p in problem:
                if p == problem_d:
                    pret = p
        return pret

    def _get_probs_done(self, course_id, user_id):
        log = self.store.get(course_id, self._get_user_log_key(user_id))
        done = []
        for interaction in log:
            if interaction['type'] == 'response':
                if interaction['problem'] not in done:
                    done.append(interaction['problem'])
        return done

    def _get_remaining_by_user(self, course_id, user_id):
        all = self.store.get(course_id, 'problems')
        done = self._get_probs_done(course_id, user_id)
        remaining = [x for x in all if x not in done]
        return remaining

    def _get_and_assert_problem_exists(self, course_id, problem_dict):
        problems = self.store.get(course_id, 'problems')
        if problem_dict not in problems:
            # still try to look up the problem
            if 'problem_name' not in problem_dict:
                raise interface.DataException("Next problem not in database, "
                                              "and does not contain problem_name: {}".format(str(problem_dict)))
            problem_dict = self._get_problem(course_id, problem_dict['problem_name'])
            # above line will raise exception if it can't be found
        return problem_dict


COLL_SUFFIX = {'log': '_log', 'user_problem': '_problems'}


class CourseRepositoryMongo(CourseRepository):
    """
    Interface implementation for MongoDB backend
    """
    def post_course(self, course_id):
        """
        Create courses related document in Courses collection

        :param course_id: ID of the Course
        """
        coll_log = course_id + COLL_SUFFIX['log']
        coll_user_problem = course_id + COLL_SUFFIX['user_problem']
        self.store.create_table('Courses')
        self.store.create_table(
            coll_log, index_fields=[
                ['student_id', 'ascending'],
                ['timestamp', 'descending'],
                ['problem.problem_name', 'ascending'],
                ['attempt', 'ascending']
            ],
            index_unique=True)
        self.store.create_table(coll_user_problem, index_fields=[['student_id', 'ascending']])
        data_dict = {
            'course_id': course_id,
            'users_in_progress': [],
            'users_finished': [],
            'skills': [],
            'problems': [],
            'experiments': []
        }
        self.store.record_data(table='Courses', data=data_dict)

    def post_skill(self, course_id, skill_name):
        """
        Add skill in courses.skills field
        :param course_id: ID of the course
        :param skill_name: name of the added skill
        """
        self.store.course_append(course_id, 'skills', skill_name)

    def _add_problem(self, course_id, skill_names, problem_name, tutor_url, b_pretest, b_posttest):
        """
        Internal class method for problem fulfilling

        :param course_id: ID of the Course
        :param skill_names: list of skills names
        :param problem_name: string of problem name
        :param tutor_url: string with tutor url
        :param b_pretest: boolean flag to mark problem as pretest
        :param b_posttest: boolean flag to mark problem as posttest
        """
        unknown_skills = set(skill_names) - set(self.store.course_get(course_id, 'skills'))
        if unknown_skills:
            raise interface.DataException("No such skill(s): {}".format(list(unknown_skills)))
        self.store.course_append(
            course_id, 'problems', {
                'problem_name': problem_name,
                'tutor_url': tutor_url,
                'pretest': b_pretest,
                'posttest': b_posttest,
                'skills': skill_names
            }
        )

    def enroll_user(self, course_id, user_id):
        coll = course_id + COLL_SUFFIX['user_problem']
        self.store.course_append(course_id, 'users_in_progress', user_id)
        self.store.record_data(coll, {'student_id': user_id, 'current': None, 'next': None})

    def get_skills(self, course_id):
        return self.store.course_get(course_id, 'skills')

    def get_course_ids(self):
        return self.store.get_tables()

    def get_problems(self, course_id, skill_name=None):
        """
        Get all problems related to this course-skill pre-test, normal, and post-test

        :param course_id: string ID of the course
        :param skill_name: string (optional) name of the skill
        :return: list of problems
        """
        problems = self.store.course_get(course_id, 'problems')
        if skill_name:
            return [problem for problem in problems if skill_name in problem['skills']]
        return problems

    def get_in_progress_users(self, course_id):
        return self.store.course_get(course_id, 'users_in_progress')

    def get_finished_users(self, course_id):
        return self.store.course_get(course_id, 'users_finished')

    def _get_problem(self, course_id, problem_name):
        problems = self.store.course_search(
                course_id, 'problems', {'problem_name': problem_name}, 'problems', {'problem_name': problem_name}
        ).get('problems')
        if problems:
            return problems[0]
        else:
            raise interface.DataException("Problem not found: {}".format(problem_name))

    def post_interaction(self, course_id, problem_name, user_id, correct, attempt, unix_seconds):
        """
        Store interaction notification in the database ..._log collection

        :param course_id: course id
        :param problem_name: name of the problem
        :param user_id: student id
        :param correct: boolean flag to mark answer is correct or not
        :param attempt: number of attempts to answer the problem
        :param unix_seconds: timestamp
        """
        problem = self._get_problem(course_id, problem_name)
        if not problem:
            raise interface.DataException("Problem {} not in Course generic problems list".format(problem_name))
        data = {
            'student_id': user_id,
            'problem': problem,
            'correct': correct,
            'attempt': attempt,
            'unix_s': unix_seconds, 'type': 'response',
            'timestamp': datetime.fromtimestamp(unix_seconds).strftime('%Y-%m-%d %H:%M:%S')
        }
        coll = course_id + COLL_SUFFIX['log']
        self.store.record_data(coll, data)

        if not self.get_all_remaining_posttest_problems(course_id, user_id):
            self.store.course_user_done(course_id, user_id)

    def post_load(self, course_id, problem_name, user_id, unix_seconds):
        """
        Store logging notification about loading page with the problem

        :param course_id: course id
        :param problem_name: name of the problem
        :param user_id: student id
        :param unix_seconds: timestamp
        """
        problem = self._get_problem(course_id, problem_name)
        coll = course_id + COLL_SUFFIX['log']
        data = {
            'student_id': user_id,
            'problem': problem,
            'unix_s': unix_seconds,
            'type': 'page_load',
            'timestamp': datetime.fromtimestamp(unix_seconds).strftime('%Y-%m-%d %H:%M:%S')
        }
        # NOTE(idegtiarov) checking that load was already stored for this problem doesn't need if we are interesting in
        # correct statistic and logging additional/same data is ok
        self.store.record_data(coll, data)

    def set_next_problem(self, course_id, user_id, problem_dict):
        """
        Set problem described in problem_dict as next in collection ..._problem

        :param course_id: course id
        :param user_id:  student id
        :param problem_dict: dict with problem description
        """
        coll = course_id + COLL_SUFFIX['user_problem']
        update_dict = {'$set': {'next': problem_dict}}
        self.store.update_doc(coll, {'student_id': user_id}, update_dict)

    def advance_problem(self, course_id, user_id):
        coll = course_id + COLL_SUFFIX['user_problem']
        current_problem = self.store.get_one(coll, user_id, 'next')
        self.store.update_doc(coll, {'student_id': user_id}, {'$set': {'current': current_problem, 'next': None}})

    def _get_remaining_by_user(self, course_id, user_id):
        coll = course_id + COLL_SUFFIX['log']
        done = self.store.get_statistic(
            coll, user_id, {'type': 'response'}, 'done', op='$addToSet', op_value='$problem')
        if done.alive:
            done = done.next()['done']
            return [problem for problem in self.get_problems(course_id) if problem not in done]
        else:
            return self.get_problems(course_id)

    def post_experiment(self, course_id, experiment_name, start, end):
        experiment = {'experiment_name': experiment_name, 'start_time': start, 'end_time': end}
        self.store.course_append(course_id, 'experiments', experiment)

    def get_experiments(self, course_id):
        return self.store.course_get(course_id, 'experiments')

    def get_experiment(self, course_id, experiment_name):
        return self.store.course_search(
            course_id,
            'experiments',
            {'experiment_name': experiment_name},
            'experiments',
            {'experiment_name': experiment_name}
        )['experiments'][0]

    def delete_experiment(self, course_id, experiment_name):
        self.store.update_doc(
            'Courses', {'course_id': course_id}, {'$pull': {'experiments': {'experiment_name': experiment_name}}}
        )

    def get_subjects(self, course_id, experiment_name):
        experiment = self.get_experiment(course_id, experiment_name)
        users = self.get_finished_users(course_id)
        coll = course_id + COLL_SUFFIX['log']
        subjects = self.store.get_statistic(
            coll,
            course_id,
            {'student_id': {'$in': users}, 'problem.posttest': True, 'unix_s': {'$lt': experiment['end_time']}},
            group_key='subjects',
            op='addToSet',
            op_value='$student_id'
        )
        return subjects['subjects'] if subjects.alive else []

    def get_raw_user_data(self, course_id, user_id):
        coll = course_id + COLL_SUFFIX['log']
        return self.store.get_user_logs(coll, user_id)

    def get_raw_user_skill_data(self, course_id, skill_name, user_id):
        coll = course_id + COLL_SUFFIX['log']
        return self.store.get_user_logs(coll, user_id, add_filter={'problem.skills': skill_name})

    def get_next_problem(self, course_id, user_id):
        coll = course_id + COLL_SUFFIX['user_problem']
        return self.store.get_one(coll, user_id, 'next')

    def get_current_problem(self, course_id, user_id):
        coll = course_id + COLL_SUFFIX['user_problem']
        return self.store.get_one(coll, user_id, 'current')

    def get_all_interactions(self, course_id, user_id):
        coll = course_id + COLL_SUFFIX['log']
        return self.store.get_user_logs(
            coll,
            user_id,
            add_filter={'type': 'response', 'attempt': 1},
            project={'problem': 1, 'correct': 1, 'unix_s': 1}
        )

    def get_interactions(self, course_id, skill_name, user_id):
        coll = course_id + COLL_SUFFIX['log']
        return self.store.get_user_logs(
            coll,
            user_id,
            add_filter={'problem.skills': skill_name, 'type': 'response', 'attempt': 1},
            project={'problem': 1, 'correct': 1, 'unix_s': 1}
        )

    def get_whole_trajectory(self, course_id, user_id):
        coll = course_id + COLL_SUFFIX['log']
        return self.store.get_user_logs(
            coll, user_id, add_filter={'type': 'response', 'attempt': 1}, get_from_doc='correct'
        )

    def get_skill_trajectory(self, course_id, skill_name, user_id):
        coll = course_id + COLL_SUFFIX['log']
        return self.store.get_user_logs(
            coll,
            user_id,
            add_filter={'problem.skills': skill_name, 'type': 'response', 'attempt': 1},
            get_from_doc='correct'
        )
