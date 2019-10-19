// ==UserScript==
// @name         Tau Station Universal Tracker
// @version      1.1
// @author       Moritz Lenz <moritz.lenz@gmail.com>
// @description  General data collection script for Tau Station. Please get an access token from moritz and add it in your preferences page.
// @match        https://alpha.taustation.space/
// @match        https://alpha.taustation.space/*
// @require      https://code.jquery.com/jquery-3.3.1.min.js
// @require      https://rawgit.com/taustation-fan/userscripts/master/userscript-preferences.js
// @downloadURL  https://github.com/taustation-fan/universal-tau-tracker/raw/master/tau-tracker.user.js
// @grant        none
// ==/UserScript==

// UI code shamelessly stolen from tauhead_data_gatherer.user.js
// with s/tauhead/utt/g

var game_mobile_message_section;
var game_mobile_message_list;
var game_desktop_message_section;
var game_desktop_message_list;
var game_character_message_items;
var utt_init_message_ui_done;


function utt_add_message(message, color) {
    if (!utt_init_message_ui_done) {
        utt_init_message_ui();
    }

    if (!color) {
        color = "green";
    }

    let message_shown = false;

    if ( game_mobile_message_list.length === 1 ) {
        game_mobile_message_list.append(
            "<li style='background-color: "+color+";'>" +
            "Tau Tracker: " +
            message +
            "</li>"
        );
        message_shown = true;
    }

    if ( game_desktop_message_list.length === 1 ) {
        game_desktop_message_list.append(
            "<li style='background-color: "+color+";'>" +
            "Tau Tracker: " +
            message +
            "</li>"
        );
        message_shown = true;
    }

    if ( !message_shown ) {
        $(th_message).append(
            "<div style='background-color: "+color+";'>" +
            message +
            "</div>"
        );
    }
}

function utt_populate_mobile_message_vars() {
    game_mobile_message_section = $("#main-content > section[aria-label='Feedback']").first();
    game_mobile_message_list    = $(game_mobile_message_section).find("ul#character-messages").first();
}

function utt_populate_desktop_message_vars() {
    game_desktop_message_section = $("#main-content > .content-section > section[aria-label='Action Feedback']").first();
    game_desktop_message_list    = $(game_desktop_message_section).find("ul.character-messages-desktop").first();
}

function utt_init_message_ui() {
    if (utt_init_message_ui_done) {
        return;
    }

    if (!game_mobile_message_section) {
        utt_populate_mobile_message_vars();
    }

    if (!game_desktop_message_section) {
        utt_populate_desktop_message_vars();
    }

    if ( game_mobile_message_section.length === 0 ) {
        utt_init_button_ui();
        utt_init_message_ui_done = true;
        return;
    }

    if ( game_desktop_message_section.length === 0 ) {
        game_desktop_message_section = game_mobile_message_section;
    }

    if ( !game_mobile_message_list || game_mobile_message_list.length === 0 ) {
        game_mobile_message_list = $("<ul id='character-messages' class='messages character-messages-mobile' role='alert' area-label='Action Feedback'></ul>");
        game_mobile_message_section.append(game_mobile_message_list);
    }

    // If we're re-using the mobile section for the desktop,
    // don't add the message twice
    if ( !game_mobile_message_section.is( game_desktop_message_section ) ) {
        if ( !game_desktop_message_list || game_desktop_message_list.length === 0 ) {
            game_desktop_message_list = $("<ul class='messages character-messages-desktop' role='alert' area-label='Action Feedback'></ul>");
            game_desktop_message_section.append(game_desktop_message_list);
        }
    }

    utt_init_message_ui_done = true;
}
// end stuff stolen from tauhead


function get_station() {
    var full_station = $('span.station').text().trim();
    var match = full_station.match(/([^,]+), (.*?)\s+system/);
    if (match) {
        return {
            station: match[1],
            system: match[2],
        }
    }
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
        utt_add_message('Please configure your access token in the user preferences', 'orange');
        return;
    }

    if ($('#employment-nav-heading').length == 0) {
        utt_add_message('Cannot extract all necessary data while the "Current Ventures" box is missing', 'orange')
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
        utt_add_message('No career tasks found', 'orange')
        return;
    }

    var payload = {
        token: options.token,
        station: station.station,
        system: station.system,
        career: career,
        rank: rank,
        tasks: tasks,
    };

    let url = options.base_url + 'v1/career-task/add';

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
                utt_add_message(message);
            }
            else {
                utt_add_message('error recording tasks: ' + response.message, 'orange');
            }
        },
        error: function(xhr) {
            utt_add_message('cannot talk to ' + url + ': ' + xhr.response_text, 'orange');
        },
    });
}

function extract_local_shuttles(options, station) {
    var token = options.token;
    if (!token) {
        utt_add_message('Please configure your access token in the user preferences', 'orange');
        return;
    }

    var schedules = [];
    // var departure = $('html').data('time');
    $('.area-table-item').each(function() {
        let $table = $(this);
        let destination = $table.find('.area-table-title span').text();
        let distances = [];
        $table.find('li.ticket-schedule-row').each(function() {
            let $row = $(this);
            let distance = parseInt($row.find('.ticket-col-distance').find('dd').text().replace(/\s*km/, ''), 10);
            let departure = $row.find('.ticket-col-departure').find('dd').text();
            let travel_time = $row.find('.ticket-col-travel-time').find('dd').text()
            if (distance && departure) {
                distances.push([departure, distance, travel_time]);
            }
        });
        if (distances.length) {
            schedules.push({'destination': destination, 'distances': distances});
        }
    })
    if (schedules.length == 0) {
        return;
    }
    var payload = {
        token: token,
        source: station.station,
        system: station.system,
        schedules: schedules,
    }
    let url = options.base_url + 'v1/distance/add';

    $.ajax({
        type: "POST",
        url: url,
        dataType: 'json',
        data: JSON.stringify(payload),
        success: function(response) {
            if (response.recorded) {
                utt_add_message(response.message);
            }
            else {
                utt_add_message('error station distances: ' + response.message, 'orange');
            }
        },
        error: function(xhr) {
            utt_add_message('cannot talk to ' + url + ': ' + xhr.response_text, 'orange');
        },
    });
}

function extract_docks(options, station) {
    var token = options.token;
    if (!token) {
        utt_add_message('Please configure your access token in the user preferences', 'orange');
        return;
    }
    if ($('html').hasClass('cockpit')) {
        extract_docks_cockpit(token, options, station);
    }
    else {
        extract_docks_fuel(token, options, station);
    }
}

function extract_docks_cockpit(token, options, station) {
    var departure = $('html').data('time');
    var schedules = [];
    $('.area-table-item').each(function() {
        let $table = $(this);
        let distances = [];
        let destination = $table.find('.area-table-title').find('span').text();

        $table.find('li.ticket-schedule-row').each(function() {
            let $row = $(this);
            let distance = parseInt($row.find('.ticket-col-distance').find('dd').text().replace(/\s*km/, '').replace(',', ''), 10)
            if (departure.length) {
                distances.push([departure, distance]);
            }
        });
        if (distances.length) {
            schedules.push({'destination': destination, 'distances': distances});
        }
    });
    if (schedules.length == 0) {
        return;
    }
    var payload = {
        token: token,
        source: station.station,
        system: station.system,
        schedules: schedules,
    }

    let url = options.base_url + 'v1/distance/add';

    $.ajax({
        type: "POST",
        url: url,
        dataType: 'json',
        data: JSON.stringify(payload),
        success: function(response) {
            if (response.recorded) {
                utt_add_message(response.message);
            }
            else {
                utt_add_message('error station distances: ' + response.message, 'orange');
            }
        },
        error: function(xhr) {
            utt_add_message('cannot talk to ' + url + ': ' + xhr.response_text, 'orange');
        },
    });
}

function extract_docks_fuel(token, options, station) {
    let url = options.base_url + 'v1/fuel/add';
    $('div.own-ship-details').each(function() {
        var $ship = $( this );
        var $meter = $ship.find('.ship-state').find('div:contains("Fuel:")').find('.meter');
        var value_now = parseFloat($meter.attr('aria-valuenow'), 10)
        var value_max = parseFloat($meter.attr('aria-valuemax'), 10)
        var fuel_g = value_max - value_now;
        if (!fuel_g) return;
        var price = parseFloat($ship.find('a:contains(Refuel)').find('.currency-amount').text())
        if (!price) return;

        var payload = {
            token: token,
            station: station.station,
            system: station.system,
            fuel_g: fuel_g,
            price: price,
        };
        $.ajax({
            type: "POST",
            url: url,
            dataType: 'json',
            data: JSON.stringify(payload),
            success: function(response) {
                if (response.recorded) {
                    let message = 'Fuel price recorded. +1 brownie point!<br>' + response.message;
                    utt_add_message(message);
                }
                else {
                    utt_add_message('error recording fuel price: ' + response.message, 'orange');
                }
            },
            error: function(xhr) {
                utt_add_message('cannot talk to ' + url + ': ' + xhr.response_text, 'orange');
            },
        });
    });
}

(function() {
    'use strict';
    let base_url = 'https://tracker.tauguide.de/';

    function pref_specs() {
        return {
            key: 'career_tracker',
            label: 'Universal Tau Tracker',
            options: [
                {
                    key: 'token',
                    label: 'Access Token',
                    type: 'text',
                    default: '',
                },
                {
                    key: 'base_url',
                    label: 'Base API URL (leave empty for default)',
                    type: 'text',
                    default: '',
                }
            ],
        };
    }

    var station = get_station();
    // must always be called, otherwise preference editing breaks
    let options = userscript_preferences( pref_specs() );
    if (!options.base_url) {
        options.base_url = base_url;
    }
    if (!station) {
        return;
    }
    let path = window.location.pathname;
    (function() {
        let url = options.base_url + 'v1/career-task/station-needs-update/' + encodeURIComponent(station.system) + '/' + encodeURIComponent(station.station);
        $.get(url, function (response) {
            if (response.needs_update) {
                $('span.employment-title:contains(Career)').parent().append('– <a href="/career">Check tasks</a>');
            }
        });
    })()

    if (path.match('^/career')) {
        record_career_tasks(options, station);
    } else if (path.match('^/area/local-shuttles')) {
        extract_local_shuttles(options, station);
    }
    else if (path.match('^/area/docks')) {
        extract_docks(options, station);
    }
}());
