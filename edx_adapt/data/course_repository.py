"""Repository that implements DataInterface using a tinydb backend """

from datetime import datetime

import interface
from edx_adapt import logger

COLL_SUFFIX = {'log': '_log', 'user_problem': '_problems'}


class CourseRepositoryMongo(interface.DataInterface):
    """
    Interface implementation for MongoDB backend
    """
    def __init__(self, storage_module):
        super(CourseRepositoryMongo, self).__init__(storage_module)
        try:
            # @type self.store: StorageInterface
            self.store.create_table("Generic", [['key', 'ascending']], index_unique=True)
            self.store.create_table('Courses', index_fields=[['course_id', 'ascending']], index_unique=True)
        except interface.DataException:
            logger.exception("(Generic table already existing is okay) Make sure this isn't a problem:")
            pass

    def post_course(self, course_id):
        """
        Create courses related document in Courses collection

        :param course_id: ID of the Course
        """
        coll_log = course_id + COLL_SUFFIX['log']
        coll_user_problem = course_id + COLL_SUFFIX['user_problem']
        self.store.create_table(
            coll_log, index_fields=[
                ['student_id', 'ascending'],
                ['timestamp', 'descending'],
                ['problem.problem_name', 'ascending'],
                ['attempt', 'ascending']
            ],
            index_unique=True)
        self.store.create_table(coll_user_problem, index_fields=[['student_id', 'ascending']], index_unique=True)
        data_dict = {
            'course_id': course_id,
            'model_params': [],
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

    def post_problem(self, course_id, skill_names, problem_name, tutor_url):
        self._add_problem(course_id, skill_names, problem_name, tutor_url, False, False)

    def post_pretest_problem(self, course_id, skill_names, problem_name, tutor_url):
        self._add_problem(course_id, skill_names, problem_name, tutor_url, True, False)

    def post_posttest_problem(self, course_id, skill_names, problem_name, tutor_url):
        self._add_problem(course_id, skill_names, problem_name, tutor_url, False, True)

    def enroll_user(self, course_id, user_id):
        coll = course_id + COLL_SUFFIX['user_problem']
        self.store.course_append(course_id, 'users_in_progress', user_id)
        self.store.record_data(coll, {'student_id': user_id, 'current': None, 'next': None})

    def post_model_params(self, course_id, prob_list, new=False):
        """
        Add default probability (or set of model_params) student's skills are enrolled with.

        :param course_id: course id
        :param prob_list: list of dicts with probability parameters: [
            { "threshold": 0.9, "ps": 0.01, "pi": 0.1, "pg": 0.01, "pt": 0.6},
            { "threshold": 0.95, "ps": 0.25, "pi": 0.2, "pg": 0.25, "pt": 0.5}
        ]
        :param new: boolean flag to mark that old model_params are replaced by new
        """
        if isinstance(prob_list, list):
            self.store.update_doc(
                'Courses',
                {'course_id': course_id},
                {('$set' if new else '$addToSet'): {'model_params': prob_list}},
                new=new
            )
        else:
            logger.error("Model_params are not given in a list: {}".format(prob_list))
            raise interface.DataException("Incorrect type of the prob_list parameter")

    def get_model_params(self, course_id):
        """
        Return default model_params stored in the database.

        :param course_id: Course ID
        :return: list of probability parameters
        """
        return self.store.course_get(course_id, 'model_params')

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

    def get_num_pretest(self, course_id, skill_name):
        pretest = [x for x in self.get_problems(course_id, skill_name) if x['pretest'] is True]
        return len(pretest)

    def get_num_posttest(self, course_id, skill_name):
        posttest = [x for x in self.get_problems(course_id, skill_name) if x['posttest'] is True]
        return len(posttest)

    def get_in_progress_users(self, course_id):
        return self.store.course_get(course_id, 'users_in_progress')

    def get_finished_users(self, course_id):
        return self.store.course_get(course_id, 'users_finished')

    def _get_problem(self, course_id, problem_name):
        problems = self.store.course_search(
                course_id, 'problems', {'problem_name': problem_name}, 'problems', {'problem_name': problem_name}
        )
        if problems:
            return problems.get('problems')[0]
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

    def get_all_remaining_problems(self, course_id, user_id):
        return [x for x in self._get_remaining_by_user(course_id, user_id)
                if x['pretest'] is False and x['posttest'] is False]

    def get_remaining_problems(self, course_id, skill_name, user_id):
        remaining = self.get_all_remaining_problems(course_id, user_id)
        return [x for x in remaining if skill_name in x['skills']]

    def get_all_remaining_posttest_problems(self, course_id, user_id):
        return [x for x in self._get_remaining_by_user(course_id, user_id) if x['posttest'] is True]

    def get_remaining_posttest_problems(self, course_id, skill_name, user_id):
        remaining = self.get_all_remaining_posttest_problems(course_id, user_id)
        return [x for x in remaining if skill_name in x['skills']]

    def get_all_remaining_pretest_problems(self, course_id, user_id):
        return [x for x in self._get_remaining_by_user(course_id, user_id) if x['pretest'] is True]

    def get_remaining_pretest_problems(self, course_id, skill_name, user_id):
        remaining = self.get_all_remaining_pretest_problems(course_id, user_id)
        return [x for x in remaining if skill_name in x['skills']]

    def _get_remaining_by_user(self, course_id, user_id):
        coll = course_id + COLL_SUFFIX['log']
        done = self.store. get_statistics(
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

    def set(self, key, value):
        logger.info("GENERIC DB_SET GOING DOWN!")
        logger.info("KEY: {}".format(str(key)))
        logger.info("VAL: {}".format(str(value)))
        self.store.set('Generic', key, value)
        logger.info("GENERIC DB_SET DONE!")

    def get(self, key):
        logger.info("GENERIC DB_GET GRABBING: {}".format(str(key)))
        return self.store.get('Generic', key)

    def _get_user_log_key(self, user_id):
        return user_id + "_log"

    def _get_user_problem_key(self, user_id):
        return user_id + "_cur_next"

    def get_subjects(self, course_id, experiment_name):
        experiment = self.get_experiment(course_id, experiment_name)
        users = self.get_finished_users(course_id)
        coll = course_id + COLL_SUFFIX['log']
        subjects = self.store. get_statistics(
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
