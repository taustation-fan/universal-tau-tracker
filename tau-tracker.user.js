// ==UserScript==
// @name         Tau Station Universal Tracker
// @version      1.13
// @author       Moritz Lenz <moritz.lenz@gmail.com>
// @description  General data collection script for Tau Station. Please get an access token from moritz and add it in your preferences page.
// @match        https://taustation.space/*
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


function enrich_version(payload) {
    payload.script_version = GM_info.script.version;
    return payload;
}

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
        data: JSON.stringify(enrich_version(payload)),
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
            let price = parseFloat($row.find('.ticket-col-fare').find('dd').find('span').find('span').text())
            if (distance && departure) {
                distances.push([departure, distance, travel_time, price]);
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
        data: JSON.stringify(enrich_version(payload)),
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
function get_ships() {
    const ships = [];
    const character = $('.avatar-links--item--player').text().replace(/\s+.*/, '');

    // Own ships
    $('div.own-ships-container h3 button').each(function() {
        const $ship = $(this);
        const name = $ship.find('span.name').text().replace(/:\s*$/, '');
        const ship_class = $ship.find('span.class').text();
        const registration = $ship.attr('aria-controls').replace('ship-', '');
        ships.push({
            name: name,
            captain: character,
            registration: registration,
            class: ship_class,
        });
    });

    // Other's ships
    $('.ticket-schedule-row').each(function() {
        var $ship = $( this );
        if ($ship.find('.ticket-col-head').length) {
            return;
        }
        const ship_name = $ship.find('.docked-ships-col-name').find('dd').text();
        if (ship_name === null)
            return;
        const captain_name = $ship.find('.docked-ships-col-captain').find('a').text();

        const $details = $ship.parent('ul').next();
        const details = {}
        $details.find('.ship-state').find('div').each(function () {
            var $d = $( this );
            var name = $d.find('dt').text().replace(':', '');
            var value = $d.find('dd').text();
            details[name] = value;
        });
        ships.push({
            name: ship_name,
            captain: captain_name,
            registration: details['Registration'],
            class: details['Class'],
        })

    });
    return ships;
}

function extract_docks_ships(token, options, station) {
    const ships = get_ships();
    const payload = {
        token: token,
        station: station.station,
        system: station.system,
        ships: ships,
    }
    let url = options.base_url + 'v1/ship/add';

    $.ajax({
        type: "POST",
        url: url,
        dataType: 'json',
        data: JSON.stringify(enrich_version(payload)),
        success: function(response) {
            if (response.success) {
                if (response.message)
                    utt_add_message(response.message);
            }
            else if (response.meessage) {
                utt_add_message('error recording ships: ' + response.message, 'orange');
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
        extract_docks_ships(token, options, station);
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
        data: JSON.stringify(enrich_version(payload)),
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
    let prices = [];
    $('div.own-ship-details').each(function() {
        var $ship = $( this );
        var $meter = $ship.find('.ship-state').find('div:contains("Fuel:")').find('.meter');
        var value_now = parseFloat($meter.attr('aria-valuenow'), 10)
        var value_max = parseFloat($meter.attr('aria-valuemax'), 10)
        var fuel_g = value_max - value_now;
        if (!fuel_g) return;
        var price = parseFloat($ship.find('a:contains(Refuel)').find('.currency-amount').text())
        if (!price) return;
        prices.push({
            price: price,
            fuel_g: fuel_g,
        });
    });
    if (!prices.length)
        return;

    prices.sort(function (a, b) {
        b.fuel_g - a.fuel_g;
    });
    const p = prices[0];

    var payload = {
        token: token,
        station: station.station,
        system: station.system,
        fuel_g: p.fuel_g,
        price: p.price,
    };
    $.ajax({
        type: "POST",
        url: url,
        dataType: 'json',
        data: JSON.stringify(enrich_version(payload)),
        success: function(response) {
            if (response.recorded) {
                let message = '';
                if (options.compact_fuel_display){
                    message = 'Fuel price recorded. +1 brownie point!<br><details><summary>Latest fuel prices</summary>' + response.message + '</details>';
                } else {
                    message = 'Fuel price recorded. +1 brownie point!<br>' + response.message;
                }
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
}

function extract_vendor(options, station) {
    let url = options.base_url + 'v1/vendor-inventory/add';
    let token = options.token;
    if (!token) {
        utt_add_message('Please configure your access token in the user preferences', 'orange');
        return;
    }
    let vendor = $('h2.vendor-details-heading').text();
    let vendor_items = [];
    $('button.item.modal-toggle').each( function() {
        let btn = $( this )[0];
        let item_slug = btn.getAttribute('data-item-name');
        // let name_span = btn.getElementsByClassName('name')[0];
        // let item_category = name_span.childNodes[1].innerText.replace(/:$/, '');
        // let item_name = name_span.childNodes[2].nodeValue.trim();
        let currency_span = btn.getElementsByClassName('currency')[0];
        let item_price_str = currency_span.childNodes[1].innerText;
        let item_price = parseFloat( item_price_str.replaceAll(',', '') );
        let item_currency = currency_span.childNodes[4].innerText;
        vendor_items.push({
            slug:       item_slug,
            price:      item_price,
            currency:   item_currency,
        });
    });
    if (!vendor_items.length)
        return;

    let payload = {
        token:      token,
        station:    station.station,
        system:     station.system,
        vendor:     vendor,
        inventory:  vendor_items,
    };
    $.ajax({
        type: "POST",
        url: url,
        dataType: 'json',
        data: JSON.stringify(enrich_version(payload)),
        success: function(response) {
            if (response.recorded) {
                let message = 'Vendor inventory recorded. +1 brownie point!<br>' + response.message;
                utt_add_message(message);
            }
            else {
                utt_add_message('error recording vendor inventory: ' + response.message, 'orange');
            }
        },
        error: function(xhr) {
            utt_add_message('cannot talk to ' + url + ': ' + xhr.response_text, 'orange');
        },
    });
}

function extract_item(options) {
    let url = options.base_url + 'v1/item/add';
    let token = options.token;
    if (!token) {
        utt_add_message('Please configure your access token in the user preferences', 'orange');
        return;
    }

    let loc = location.href.split('/').pop();
    let item_slug = loc.split('?')[0]; // remove any potential GET parameters
    let item_name = $('h1.name').text();
    if (!item_name)
        return;

    let item_rarity = $('li.rarity').find('span').text();
    let item_mass = $('li.weight').find('span').text();
    let item_mass_kg = parseFloat( item_mass.replace(' kg', '') );
    let item_tier = parseInt( $('li.tier').find('span').text() );
    let item_type = $('li.type').find('span').text();
    let item_desc = $('p.item-detailed-description').text();

    let item_stats = {}
    if (item_type == 'Weapon') {
        item_stats = extract_item_weapon();
    } else if (item_type == 'Armor') {
        item_stats = extract_item_armor();
    } else if (item_type == 'Medical') {
        item_stats = extract_item_medical();
    } else if (item_type == 'Food') {
        item_stats = extract_item_food(item_desc);
    }

    let payload = Object.assign(
        {
            "token":    token,
            "slug":     item_slug,
            "name":     item_name,
            "mass_kg":  item_mass_kg,
            "rarity":   item_rarity,
            "type":     item_type,
            "tier":     item_tier,
            "description": item_desc,
        },
        item_stats
    );
    $.ajax({
        type: "POST",
        url: url,
        dataType: 'json',
        data: JSON.stringify(enrich_version(payload)),
        success: function(response) {
            if (response.recorded) {
                let message = 'Item recorded. +1 brownie point!<br>' + response.message;
                utt_add_message(message);
            }
            else {
                utt_add_message('error recording item: ' + response.message, 'orange');
            }
        },
        error: function(xhr) {
            utt_add_message('cannot talk to ' + url + ': ' + xhr.response_text, 'orange');
        },
    });
}

function extract_item_weapon() {
    let accuracy  = parseFloat( $('li.accuracy').find('span').text() );
    let piercing  = parseFloat( $('li.piercing-damage').find('span').text() );
    let impact    = parseFloat( $('li.impact-damage').find('span').text() );
    let energy    = parseFloat( $('li.energy-damage').find('span').text() );
    let wpntype   = $('li.weapon_type').find('span').text();
    let range     = $('li.range').find('span').text();
    let hand2hand = ( $('li.hand-to-hand').find('span').text() == 'Yes' );
    return {
        "accuracy":         accuracy,
        "hand_to_hand":     hand2hand,
        "range":            range,
        "weapon_type":      wpntype,
        "piercing_damage":  piercing,
        "impact_damage":    impact,
        "energy_damage":    energy,
    };
}

function extract_item_armor() {
    // yes, Taustation uses "damage" for the defense stats
    let piercing  = parseFloat( $('li.piercing-damage').find('span').text() );
    let impact    = parseFloat( $('li.impact-damage').find('span').text() );
    let energy    = parseFloat( $('li.energy-damage').find('span').text() );
    return {
        "piercing_defense": piercing,
        "impact_defense":   impact,
        "energy_defense":   energy,
    };
}

function extract_item_medical() {
    let stats = {};
    $('ul.data-list').find('li.strength').each( function() {
        let $li = $(this);
        let stat = $li[0].childNodes[0].textContent;
        let value = $li.find('span').text();

        stat = stat.toLowerCase().replaceAll(' ', '_');
        if (stat.match('toxicity')) {
            value = value.replace('%', '');
        }
        stats[stat] = parseFloat(value);
    });
    return stats;
}

function extract_item_food(desc) {
    let match = desc.match(/This food gives (\w+)s a (\w+) (\w+) boost for (\d+) segment/);
    if (!match)
        return {};
    let target_genotype = match[1];
    let effect_size = match[2];
    let affected_stat = match[3];
    let duration_segments = parseInt(match[4]);
    return {
        target_genotype: target_genotype,
        affected_stat: affected_stat,
        effect_size: effect_size,
        duration_segments: duration_segments,
    };
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
                },
                {
                    key: 'compact_fuel_display',
                    label: 'Compact fuel display',
                    type: 'boolean',
                    default: false,
                }
            ],
        };
    }

    // must always be called, otherwise preference editing breaks
    let options = userscript_preferences( pref_specs() );
    if (!options.base_url) {
        options.base_url = base_url;
    }

    // item pages don't have a station
    let path = window.location.pathname;
    if (path.match('^/item')) {
        extract_item(options);
        return;
    }

    var station = get_station();
    if (!station) {
        return;
    }
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
    }
    else if (path.match('^/area/local-shuttles')) {
        extract_local_shuttles(options, station);
    }
    else if (path.match('^/area/docks')) {
        extract_docks(options, station);
    }
    else if (path.match('^/area/vendors/enter-shop')) {
        extract_vendor(options, station);
    }
}());
