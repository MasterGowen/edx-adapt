/*
 * This module abstracts some of the common operations of a tutor interacting with an edx_adapt server
 */

(function( edx_adapt, $, undefined) {

    //Connection information
    edx_adapt.apistr    = '/api/v1';
    edx_adapt.server    = '52.210.53.36';
    edx_adapt.apiport   = '8080';

    edx_adapt.course_id = $(".xmodule_display", window.parent.document).attr('data-course-id');

    //Convert course_id taken from the Course page into a course string compatible with EdxAdapt. E.g:
    //course_id = course-v1:University+SS001+2017_N is transformed into University/SS001/2017_N
    edx_adapt.coursestr = edx_adapt.course_id.split(':')[1].replace('+', '/');

    //Notify problem server that a problem has been graded
    //on error, dispatches send_interaction_error event
    edx_adapt.send_interaction = function(correct, attempt, user, problem) {

        data = {'problem': problem, 'correct': correct, 'attempt': attempt};

        //Post student's attempt to the server log
        $.ajax({
            url: "http://" + edx_adapt.server + ":" + edx_adapt.apiport + edx_adapt.apistr + '/course/' + edx_adapt.courseid + '/user/' + user + '/interaction',
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify(data),
            success: function (data) {
                console.log("Interaction successfully logged");
            },
            error: function (jqXHR, textStatus, err) {
                console.log("Error posting interaction: " + err + " " + textStatus);

                var event = new CustomEvent("send_interaction_error", {detail: { jqXHR: jqXHR, textStatus: textStatus,
                                                                        err: err}});
                document.dispatchEvent(event);
            }
        });

    };

    //Sends notification that the user loaded a problem
    //Fires notify_page_load_error event on error
    edx_adapt.notify_page_load = function(user, problem) {

        data = {'problem': problem};
        $.ajax({
            url: "http://" + edx_adapt.server + ":" + edx_adapt.apiport + edx_adapt.apistr + '/course/' + edx_adapt.courseid + '/user/' + user + '/pageload',
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify(data),
            success: function (data) {
                console.log("pageload logged");
                //do nothing?
            },
            error: function (jqXHR, textStatus, err) {
                console.log("Error posting pageload: " + err + " " + textStatus);

                var event = new CustomEvent("notify_page_load_error", {detail: { jqXHR: jqXHR, textStatus: textStatus,
                                                                        err: err}});
                document.dispatchEvent(event);
            }
        });

    };

    edx_adapt.get_username_sync = function() {
        //synchronously load the homepage to grab the user's name, if it isn't cached
        if (checkCookie("username")) {
            username = getCookie("username");
        } else {
            if (document.URL.search("18010") > -1) {
                $.ajax({
                    async: false,
                    url: "/course",
                    type: "GET",
                    success: function (data) {
                        //console.log("Found username!");
                        username = getUsername(data);
                    },
                    error: function (jqXHR, textStatus, err) {
                        console.log("Error: Could not load username: " + err);
                        return "";
                    }
                });
            } else {
                $.ajax({
                    async: false,
                    url: "/dashboard",
                    type: "GET",
                    success: function (data) {
                        //console.log("Found username!");
                        username = getUsername_dash(data);
                    },
                    error: function (jqXHR, textStatus, err) {
                        console.log("Error: Could not load username: " + err);
                        return "";
                    }
                });
            }
            setCookie("username", username, 5);
        }
        return username;
    };


    //This function grabs the problem name out of the URL
    //TODO: make it a bit smarter
    edx_adapt.get_problem_name = function() {
        var problemurl = document.referrer;
        problemurl = problemurl.split("?signin=return").join("");
        while (problemurl.slice(-1) == '/') {
            problemurl = problemurl.substring(0, problemurl.length - 1);
        }
        var problemname = problemurl.substring(problemurl.lastIndexOf("/") + 1);
        return problemname;
    };

    //This function checks if the user is done with their currently assigned problem
    //Fires is_complete event with the returned data, and is_complete_error event on error
    edx_adapt.is_complete = function (user, problem, retry) {
        if (retry === undefined) {
            retry = 0;
        }

        //check server for user status
        $.ajax({
            url: "http://" + edx_adapt.server + ":" + edx_adapt.apiport + edx_adapt.apistr + '/course/' + edx_adapt.courseid + '/user/' + user,
            type: "GET",
            success: function (data) {

                if (data['done_with_course']) {
                    var event = new CustomEvent("is_complete", {detail: { err: false, data: data, link:'',
                                                                        complete: true, done_with_course: true}});
                            document.dispatchEvent(event);
                }

                if (data['done_with_current'] && data['current'] != null && data['current']['problem_name'] == problem) {
                    //done w/ current problem. Redirect to next one if possible
                    if (data['okay'] == false) {

                        if (data['next'] == null) {
                            //The server just hasn't set the next problem yet. Wait and retry (for 5s)
                            if (retry < 5) {
                                setTimeout(function () {
                                    edx_adapt.is_complete(user, problem, retry + 1);
                                }, 1000);
                            }
                        } else {
                            //crap, there was an error choosing the next problem
                            var msg = "Error with user's next problem, check: " + JSON.stringify(data)
                            console.log(msg);
                            //is_complete_callback(false, msg);
                            var event = new CustomEvent("is_complete", {detail: { err: true, data: data, link:'',
                                                                        complete: false}});
                            document.dispatchEvent(event);
                        }
                    }
                    else {
                        var next = data['next'];
                        var link = next['tutor_url'];
                        var event = new CustomEvent("is_complete", {detail: { err: false, data: data, link: link,
                                                                        complete: true}});
                        document.dispatchEvent(event);
                    }
                } else {
                    //not done with current problem. Check again in a bit to make sure...
                    if (retry < 2) {
                        setTimeout(function () {
                            edx_adapt.is_complete(user, problem, retry + 1);
                        }, 1000)
                    } else {
                        //...then return not completed if it's definitely not done
                        var event = new CustomEvent("is_complete", {detail: { err: false, data: data, link:'',
                                                                        complete: false}});
                        document.dispatchEvent(event);
                    }
                }
            },
            error: function (jqXHR, textStatus, err) {
                //Shit, there was an error just loading the user's status
                var event = new CustomEvent("is_complete_error", {detail: { err: err, jqXHR: jqXHR,
                                                                    textStatus: textStatus}});
                document.dispatchEvent(event);
            }
        });

    };

    //This function will get the current logged in user's name
    //if the problem is loaded in Studio
    function getUsername(data) {
        var re = /Welcome, [a-z,0-9,A-Z]*/;
        var result = re.exec(data);
        var welcomestr = result[0];
        return welcomestr.substring(9);
    }

    //This function will get the current logged in user's name
    //if the problem is loaded in LMS
    function getUsername_dash(data) {
        return JSON.parse(getCookie("edx-user-info").replace(/\\"/g, '"').replace(/\\054/g, ',').slice(1, -1)).username;
    }

    //This checks the user status to see if the problem being loaded matches the user's current or next problem
    //Fires display_problem_request event with return info, and display_problem_request_error on error
    edx_adapt.display_problem_request = function(user, problem) {

        //screw it, display anything if it's staff
        if(user == 'staff') {
            var event = new CustomEvent("display_problem_request", {detail: { display: true}});
            document.dispatchEvent(event);
            return;
        }

        $.ajax({
            url: "http://" + edx_adapt.server + ":" + edx_adapt.apiport + edx_adapt.apistr + '/course/' + edx_adapt.courseid + '/user/' + user,
            type: "GET",
            success: function (data) {
                //data = JSON.parse(data)
                var cur = data['current'];
                var next = data['next'];
                var redirect = '';

                if (data['done_with_current']) {
                    //we can load current or next
                    if (cur != null) {
                        redirect = cur['tutor_url'];
                        if (cur['problem_name'] == problem) {
                            var event = new CustomEvent("display_problem_request", {detail: { display: true}});
                            document.dispatchEvent(event);
                            return;
                        }
                    }

                    if (next != null) {
                        if(next['tutor_url']) {
                            redirect = next['tutor_url']
                            if (next['problem_name'] == problem) {
                                var event = new CustomEvent("display_problem_request", {detail: {display: true}});
                                document.dispatchEvent(event);
                                return;
                            }
                        }
                    }

                    //nothing matched the problem, don't load
                    var event = new CustomEvent("display_problem_request",
                                                {detail: { display: false, redirect: redirect}});
                    document.dispatchEvent(event);

                } else {
                    //we can only load current
                    if (cur != null) {
                        redirect = cur['tutor_url']
                        if (cur['problem_name'] == problem) {
                            var event = new CustomEvent("display_problem_request", {detail: { display: true}});
                            document.dispatchEvent(event);
                            return;
                        }
                    }
                    var event = new CustomEvent("display_problem_request",
                                                {detail: { display: false, redirect: redirect}});
                    document.dispatchEvent(event);
                }
            },
            error: function (jqXHR, textStatus, err) {
                var event = new CustomEvent("display_problem_request_error", {detail: { err: err, jqXHR: jqXHR,
                                                                    textStatus: textStatus}});
                document.dispatchEvent(event);
            }
        });

    };

    function setCookie(cname, cvalue, exmin) {
        var d = new Date();
        d.setTime(d.getTime() + (exmin * 60 * 1000));
        var expires = "expires=" + d.toUTCString();
        document.cookie = cname + "=" + cvalue + "; " + expires;
    }

    function getCookie(cname) {
        var name = cname + "=";
        var ca = document.cookie.split(';');
        for (var i = 0; i < ca.length; i++) {
            var c = ca[i];
            while (c.charAt(0) == ' ') c = c.substring(1);
            if (c.indexOf(name) == 0) return c.substring(name.length, c.length);
        }
        return "";
    }

    function checkCookie(cname) {
        tmp = getCookie(cname);
        if (tmp == "") return false;
        return true;
    }

}( window.edx_adapt = window.edx_adapt || {}, jQuery));
