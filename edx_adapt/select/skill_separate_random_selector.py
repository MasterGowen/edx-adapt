import random

from interface import SelectInterface, SelectException
from edx_adapt.data.interface import DataException
from edx_adapt import logger


class SkillSeparateRandomSelector(SelectInterface):
    """ This is an implementation of the adaptive problem selector.
    At each time point, to goes through every skill (can be 1 skill)
    and computes the probability of getting the next problem correct.
    If the probability is less than the threshold parameter, the
    remaining problems corresponding to the skill is added to the
    candidate list, and the next problem is selected randomly from
    the candidate list with the same probability.
    """

    # List of the granularity of parameters
    # (If per course, "course"; if per skill, "skill"; if per user, "user")
    parameter_access_mode_list = ["course"]
    valid_mode_list = ["course", "user", "skill"]

    def __init__(self, data_interface, model_interface, parameter_access_mode=""):
        """
        Constructor with the running mode specified, where running mode specifies
        whether the parameters are specified per course, per user, per skill, etc.

        :param data_interface: data module storing state information about the user and the course
        :param model_interface: model interface that computes the probability of getting the next problem correct
        :param parameter_access_mode: Mode that defines the granularity of the parameters
                                      If per skill, "skill"; if per user, "user"
                                      These can be combined. ex) "user skill" - per user and skill
                                      The order must match the order of keys used in data module's set method
                                      For instance, if "user skill", key should be "user_id skill_name"
                                      Note, by default, the parameters are separate per course
                                      So if the string is empty, there is one parameter set per course
        """
        super(SkillSeparateRandomSelector, self).__init__(data_interface, model_interface)

        logger.info(self.data_interface)
        logger.info(self.model_interface)
        logger.info(self.model_interface.get_probability_correct)

        self.parameter_access_mode_list.extend(parameter_access_mode.split())
        for mode in self.parameter_access_mode_list:
            if mode not in self.valid_mode_list:
                raise SelectException("Parameter access mode is invalid")

    def _prepare_problems_list(self, course_id, user_id):
        candidate_problem_list = []  # List of problems to choose from
        for skill_name in self.data_interface.get_skills(course_id):  # For each skill
            if skill_name == 'None':
                continue
            # Gets the parameters corresponding to the course, user, skill - parameter set must include "threshold"
            skill_parameter = self.data_interface.get(self._get_key(course_id, user_id, skill_name))
            prob_correct = self.model_interface.get_probability_mastered(
                # trajectory of correctness
                self.data_interface.get_skill_trajectory(course_id, skill_name, user_id),
                skill_parameter  # parameters for the skill
            )
            # If the probability is less than threshold, add the problems to candidate list
            if prob_correct < skill_parameter['threshold']:
                problems_to_add = self.data_interface.get_remaining_problems(course_id, skill_name, user_id)
                logger.debug("Skill name: {} UNDER THRESHOLD!".format(skill_name))
                logger.debug("Adding candidates: {}".format(str(problems_to_add)))
                candidate_problem_list.extend(problems_to_add)
        return candidate_problem_list

    def choose_next_problem(self, course_id, user_id):
        """
        Choose the next problem to give to the user

        :param course_id
        :param user_id
        :return: the next problem to give to the user
        """
        try:
            # if pretest problems are left, give the next one
            pretest_problems = self.data_interface.get_all_remaining_pretest_problems(course_id, user_id)
            if pretest_problems:
                return random.choice(pretest_problems)

            # if the user has started the post-test, finish it
            if [x for x in self.data_interface.get_all_interactions(course_id, user_id) if x['problem']['posttest']]:
                post = self.data_interface.get_all_remaining_posttest_problems(course_id, user_id)
                return random.choice(post) if post else {'congratulations': True, 'done': True}

            # List of problems to choose from
            candidate_problem_list = self._prepare_problems_list(course_id, user_id)

            return random.choice(
                candidate_problem_list if candidate_problem_list
                else self.data_interface.get_all_remaining_posttest_problems(course_id, user_id)
            )
        except DataException as e:
            raise SelectException("DataException: " + e.message)

    def choose_first_problem(self, course_id, user_id):
        """
        Choose the first problem to give to the user

        :param course_id
        :param user_id
        :return: the first problem to give to the user
        """
        pretest = self.data_interface.get_all_remaining_pretest_problems(course_id, user_id)
        for prob in pretest:
            if prob['problem_name'] == 'Pre_assessment_0':
                return prob

    def _get_key(self, course_id, user_id, skill_name):
        """
        Gets the valid key to access the parameters for the specified course, user, skill
        based on the mode specified in the constructor

        :param course_id
        :param user_id
        :param skill_id
        :return: key to access the parameters in the data module
        """
        mode_id_map = {"course": course_id, "user": user_id, "skill": skill_name}
        key = ""
        for mode in self.parameter_access_mode_list:
            if mode in mode_id_map:
                key += str(mode_id_map[mode])
            else:
                raise SelectException("Parameter access mode is invalid")
        return key.strip()

    def _compose_key(self, course_id, user_id, skill_name):
        mode_id_map = {"course": course_id, "user": user_id, "skill": skill_name}

        key = ""
        for mode in self.parameter_access_mode_list:
            if mode_id_map[mode]:
                key += mode_id_map[mode]
            else:
                raise SelectException("Mode and the arguments do not match")
        return key

    def get_parameter(self, course_id, user_id=None, skill_name=None):
        return self.data_interface.get(self._compose_key(course_id, user_id, skill_name))

    def set_parameter(self, parameter, course_id=None, user_id=None, skill_name=None):
        """
        Set the parameter for the specified course, user, skill (all optional)

        :param parameter: dictionary containing the set of parameters
        :param course_id
        :param user_id
        :param skill_name
        """
        self.data_interface.set(self._compose_key(course_id, user_id, skill_name), parameter)
