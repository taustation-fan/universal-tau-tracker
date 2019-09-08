// ==UserScript==
// @name         Tau Station Universal Tracker
// @version      0.1
// @author       Moritz Lenz <moritz.lenz@gmail.com>
// @description  General data collection script for Tau Station. Please get an access token from moritz and add it in your preferences page.
// @match        https://alpha.taustation.space/
// @match        https://alpha.taustation.space/*
// @require      https://code.jquery.com/jquery-3.3.1.min.js
// @require      https://rawgit.com/taustation-fan/userscripts/master/userscript-preferences.js
// @grant        none
// ==/UserScript==

function get_station() {
    var full_station = $('span.station').text().trim();
    var match = full_station.match(/([^,]+), (.*?)\s+system/);
    if (match) {
        return {
            station: match[0],
            system: match[1],
        }
    }
}
function status_message(message) {
    $('p#ctt_msg').remove();
    $('div.career-task-container').after('<p id="ctt_msg">Career task tracker: ' + message + '</p>')
}

function format_float(f) {
    f = '' + f;   // convert to string
    if (f.length > 5) {
        f = f.substr(0, 5);
    }
    return f
}

function record_career_tasks(options, station) {
    var token = options.token;
    if (!token) {
        status_message('Please configure your access token in the user preferences');
        return;
    }

    if ($('#employment-nav-heading').length == 0) {
        status_message('Cannot extract all necessary data while the "Current Ventures" box is missing');
        return;
    }
    var career_chunks = $('div#employment_panel').find('li:Contains("Career")').find('a').text().trim().split(' - ');
    var career = career_chunks[0];
    var rank = career_chunks[1];

    var tasks = {};
    $('.table-career-tasks').each(function(table_idx) {
        $(this).find('tr').each(function() {
            var $row = $( this );
            var name = $row.find('td').eq(0).text();
            if (!name) return;
            var amount = $row.find('.currency-amount').text();
            tasks[name] = amount;
        });
    });
    if ($.isEmptyObject(tasks)) {
        status_message('No career tasks found');
        return;
    }

    var payload = {
        token: token,
        station: station.station,
        system: station.system,
        career: career,
        rank: rank,
        tasks: tasks,
    };

    let url = options.base_url + 'career-task/add';

    $.ajax({
        type: "POST",
        url: url,
        dataType: 'json',
        data: JSON.stringify(payload),
        success: function(response) {
            if (response.recorded) {
                let message = 'Tasks recorded. +1 brownie point!';
                if (response.factor) {
                    message += " <b>Current factor: " + format_float(response.factor) + '.</b> ';
                }
                if (response.system_factors) {
                    let thead = '<thead><tr><th>Station</th><th>Factor</th></tr></thead>';
                    let keys = Object.keys(response.system_factors).sort();
                    let body = '';
                    for (let i = 0; i < keys.length; i++) {
                        let factor = response.system_factors[keys[i]];
                        let station = keys[i];
                        if (factor > 1.0 ) {
                            station = '<strong>' + station + '</strong>';
                        }
                        body += '<tr><td>' + station + '</td><td>' + format_float(factor)  + '</td></tr>\n';
                    }
                    let table = '<table>' + thead + '<tbody>' + body + '</tbody></table>';
                    console.log(table);
                    message += '</p><p>Other stations in this system:</p>' + table;
                }
                else {
                    message += 'No data from other stations in this system is available right now.';
                }
                status_message(message);
            }
            else {
                status_message('error recording tasks: ' + response.message);
            }
        },
        error: function(xhr) {
            status_message('cannot talk to ' + url + ': ' + xhr.response_text);
        },
    });
}

function extract_local_shuttles(options, station) {
    var token = options.token;
    if (!token) {
        status_message('Please configure your access token in the user preferences');
        return;
    }

    var schedules = [];
    var departure = $('html').data('time');
    $('.area-table-item').each(function() {
        let $table = $(this);
        let destination = $table.find('.area-table-title span').text();
        let distances = [];
        $table.find('li.ticket-schedule-row').each(function() {
            let $row = $(this);
            let distance = $row.find('.ticket-col-distance').find('dd').text().replace(/\s*km/, '');
            if (distance.length) {
                distances.push([departure, parseInt(distance, 10)]);
            }
        });
        schedules.push({'destination': destination, 'distances': distances});
    })
    var payload = {
        token: token,
        source: station.station,
        system: station.system,
        schedules: schedules,
    }
    let url = options.base_url + 'distance/add';

    $.ajax({
        type: "POST",
        url: url,
        dataType: 'json',
        data: JSON.stringify(payload),
        success: function(response) {
            if (response.recorded) {
                let message = 'Station distances recorded. +1 brownie point!';
                status_message(message);
            }
            else {
                status_message('error station distances: ' + response.message);
            }
        },
        error: function(xhr) {
            status_message('cannot talk to ' + url + ': ' + xhr.response_text);
        },
    });
}

(function() {
    'use strict';
    let base_url = 'http://127.0.0.1:5000/v1/';

    function pref_specs() {
        return {
            key: 'career_tracker',
            label: 'Career Task Tracker',
            options: [
                {
                    key: 'token',
                    label: 'Access Token',
                    type: 'text',
                    default: '',
                }
            ],
        };
    }

    var station = get_station();
    // must always be called, otherwise preference editing breaks
    let options = userscript_preferences( pref_specs() );
    options.base_url = base_url;
    if (!station) {
        return;
    }

    if (window.location.pathname.match('^/career')) {
        record_career_tasks(options, station);
    }
    else {
        let url = base_url + 'station-needs-update/' + encodeURIComponent(station.station) + '/' + encodeURIComponent(station.system);
        console.log('getting ' + url);
        $.get(url, function (response) {
            console.log('Response: ', response);
            if (response.needs_update) {
                $('span.employment-title:contains(Career)').parent().append('– <a href="/career">Check tasks</a>');
            }
        });
    }
    if (window.location.pathname.match('^/area/local-shuttles')) {
        extract_local_shuttles()
    }
}());
