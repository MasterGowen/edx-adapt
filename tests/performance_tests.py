import unittest
from nose_selenium import SeleniumTestCase

BASE_URL = 'http://52.50.241.19'


class ProblemOpenWrongTest(SeleniumTestCase):
    def setUp(self):
        super(ProblemOpenWrongTest, self).setUp()
        self.wd.implicitly_wait(10)  # seconds
        self.wd.get(BASE_URL + "/login")

        self.wd.find_element_by_id("login-email").clear()
        self.wd.find_element_by_id("login-email").send_keys("student20@raccoongang.com")
        self.wd.find_element_by_id("login-password").clear()
        self.wd.find_element_by_id("login-password").send_keys("p20")
        self.wd.find_element_by_xpath("(//button[@type='submit'])[2]").click()

    def test_login(self):
        self.wd.find_element_by_link_text("Introduction to Statistics").click()
        self.wd.find_element_by_link_text("Courseware").click()
        self.wd.find_element_by_link_text("Pre-assessment_5").click()
        self.wd.find_elements_by_xpath('//*[contains(text(), "You\'re on the wrong problem. Please click here.")]')


if __name__ == '__main__':
    unittest.main()
