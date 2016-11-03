import unittest

from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.support.events import EventFiringWebDriver
from selenium.webdriver.support.events import AbstractEventListener

COURSE_TITLE = "Introduction to Statistics"
STUDENT_EMAIL = "student20@raccoongang.com"
PASSWORD = "p20"
SOME_PROBLEM = "Pre-assessment_5"
BASE_URL = 'http://52.50.241.19'

WD_TIMEOUT = 10  # seconds
TARGET_TIME = timedelta(seconds=5)


class ScreenshotListener(AbstractEventListener):
    def on_exception(self, exception, driver):
        screenshot_name = "exception-{0:%Y-%m-%d-%H-%M}.png".format(datetime.now())
        driver.get_screenshot_as_file(screenshot_name)
        print("Screenshot saved as '%s'" % screenshot_name)


class PerformanceTestCase(unittest.TestCase):
    def setUp(self):
        # self.wd = webdriver.Firefox()
        driver = webdriver.PhantomJS()
        self.wd = EventFiringWebDriver(driver, ScreenshotListener())
        self.wd.implicitly_wait(WD_TIMEOUT)  # seconds

    def tearDown(self):
        self.wd.quit()

    def scroll_to_element(self, element):
        try:
            self.wd.execute_script("return arguments[0].scrollIntoView();", element)

        except Exception as e:
            print 'error scrolling down web element', e


class ProblemOpenWrongTest(PerformanceTestCase):
    def setUp(self):
        super(ProblemOpenWrongTest, self).setUp()
        self.wd.get(BASE_URL + "/login")

        # Log in as a student
        self.wd.find_element_by_id("login-email").clear()
        self.wd.find_element_by_id("login-email").send_keys(STUDENT_EMAIL)
        self.wd.find_element_by_id("login-password").clear()
        self.wd.find_element_by_id("login-password").send_keys(PASSWORD)
        self.wd.find_element_by_xpath("(//button[@type='submit'])[2]").click()

        # Navigate to a Courseware of a given course
        self.wd.find_element_by_link_text(COURSE_TITLE).click()
        self.wd.find_element_by_link_text("Courseware").click()

        self.start_time = datetime.now()

    def test_login(self):
        self.wd.find_element_by_link_text(SOME_PROBLEM).click()
        # switch into the first iframe so we can find button with a text
        iframe = self.wd.find_element_by_tag_name('iframe')
        self.wd.switch_to.frame(iframe)
        self.wd.find_elements_by_xpath('//*[contains(text(), "You\'re on the wrong problem. Please click here.")]')

        now = datetime.now()
        self.assertLessEqual(now - self.start_time, TARGET_TIME)

# class ProblemSubmitTest(SeleniumTestCase):
#     def setUp(self):
#         super(ProblemSubmitTest, self).setUp()
#         self.wd.get(BASE_URL + "/login")

#         self.wd.find_element_by_id("login-email").clear()
#         self.wd.find_element_by_id("login-email").send_keys("student20@raccoongang.com")
#         self.wd.find_element_by_id("login-password").clear()
#         self.wd.find_element_by_id("login-password").send_keys("p20")
#         self.wd.find_element_by_xpath("(//button[@type='submit'])[2]").click()

#     def test_sleep(self):
#         sleep(3)

if __name__ == '__main__':
    unittest.main()
