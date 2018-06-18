# -*- coding: utf-8 -*-
#!/usr/bin/env python
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2010-2017  Serge Noiraud
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Narrative Web Page generator.

This module is used to share variables, enums and functions between all modules

"""

from unicodedata import normalize
from collections import defaultdict
from hashlib import md5
import re
import gc
import logging
from xml.sax.saxutils import escape

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.display.name import displayer as _nd
from gramps.gen.display.place import displayer as _pd
from gramps.gen.utils.db import get_death_or_fallback
from gramps.gen.lib import (EventType, Date)
from gramps.gen.plug import BasePluginManager
from gramps.plugins.lib.libgedcom import make_gedcom_date, DATE_QUALITY
from gramps.gen.plug.report import utils
from gramps.plugins.lib.libhtml import Html

LOG = logging.getLogger(".NarrativeWeb")

# define clear blank line for proper styling
FULLCLEAR = Html("div", class_="fullclear", inline=True)
# define all possible web page filename extensions
_WEB_EXT = ['.html', '.htm', '.shtml', '.php', '.php3', '.cgi']
# used to select secured web site or not
HTTP = "http://"
HTTPS = "https://"

GOOGLE_MAPS = 'https://maps.googleapis.com/maps/'
# javascript code for marker path
MARKER_PATH = """
  var marker_png = '%s'
"""

# javascript code for Google's FamilyLinks...
FAMILYLINKS = """
  var tracelife = %s

  function initialize() {
    var myLatLng = new google.maps.LatLng(%s, %s);

    var mapOptions = {
      scaleControl:    true,
      panControl:      true,
      backgroundColor: '#000000',
      zoom:            %d,
      center:          myLatLng,
      mapTypeId:       google.maps.MapTypeId.ROADMAP
    };
    var map = new google.maps.Map(document.getElementById("map_canvas"),
                                  mapOptions);

    var flightPath = new google.maps.Polyline({
      path:          tracelife,
      strokeColor:   "#FF0000",
      strokeOpacity: 1.0,
      strokeWeight:  2
    });

   flightPath.setMap(map);
  }"""

# javascript for Google's Drop Markers...
DROPMASTERS = """
  var markers = [];
  var iterator = 0;

  var tracelife = %s
  var map;
  var myLatLng = new google.maps.LatLng(%s, %s);

  function initialize() {
    var mapOptions = {
      scaleControl: true,
      zoomControl:  true,
      zoom:         %d,
      mapTypeId:    google.maps.MapTypeId.ROADMAP,
      center:       myLatLng,
    };
    map = new google.maps.Map(document.getElementById("map_canvas"),
                              mapOptions);
  };

  function drop() {
    for (var i = 0; i < tracelife.length; i++) {
      setTimeout(function() {
        addMarker();
      }, i * 1000);
    }
  }

  function addMarker() {
    var location = tracelife[iterator];
    var myLatLng = new google.maps.LatLng(location[1], location[2]);

    markers.push(new google.maps.Marker({
      position:  myLatLng,
      map:       map,
      draggable: true,
      title:     location[0],
      animation: google.maps.Animation.DROP
    }));
    iterator++;
  }"""

# javascript for Google's Markers...
MARKERS = """
  var tracelife = %s
  var map;
  var myLatLng = new google.maps.LatLng(%s, %s);

  function initialize() {
    var mapOptions = {
      scaleControl:    true,
      panControl:      true,
      backgroundColor: '#000000',
      zoom:            %d,
      center:          myLatLng,
      mapTypeId:       google.maps.MapTypeId.ROADMAP
    };
    map = new google.maps.Map(document.getElementById("map_canvas"),
                              mapOptions);
    addMarkers();
  }

  function addMarkers() {
    var bounds = new google.maps.LatLngBounds();

    for (var i = 0; i < tracelife.length; i++) {
      var location = tracelife[i];
      var myLatLng = new google.maps.LatLng(location[1], location[2]);

      var marker = new google.maps.Marker({
        position:  myLatLng,
        draggable: true,
        title:     location[0],
        map:       map,
        zIndex:    location[3]
      });
      bounds.extend(myLatLng);
      if ( i > 1 ) { map.fitBounds(bounds); };
    }
  }"""

# javascript for OpenStreetMap's markers...
OSM_MARKERS = """
  function initialize(){
    var map;
    var tracelife = %s;
    var iconStyle = new ol.style.Style({
      image: new ol.style.Icon(({
        opacity: 1.0,
        src: marker_png
      }))
    });
    var markerSource = new ol.source.Vector({
    });
    for (var i = 0; i < tracelife.length; i++) {
      var loc = tracelife[i];
      var iconFeature = new ol.Feature({
       geometry: new ol.geom.Point(ol.proj.transform([loc[0], loc[1]],
                                                     'EPSG:4326', 'EPSG:3857')),
       name: loc[2],
      });
      iconFeature.setStyle(iconStyle);
      markerSource.addFeature(iconFeature);
    }
    markerLayer = new ol.layer.Vector({
      source: markerSource,
      style: iconStyle
    });
    var centerCoord = new ol.proj.transform([%s, %s], 'EPSG:4326', 'EPSG:3857');
    map= new ol.Map({
                 target: 'map_canvas',
                 layers: [new ol.layer.Tile({ source: new ol.source.OSM() }),
                          markerLayer],
                 view: new ol.View({ center: centerCoord, zoom: %d })
                 });
    var element = document.getElementById('popup');
    var tooltip = new ol.Overlay({
      element: element,
      positioning: 'bottom-center',
      stopEvent: false
    });
    map.addOverlay(tooltip);
    var displayFeatureInfo = function(pixel) {
      var feature = map.forEachFeatureAtPixel(pixel, function(feature, layer) {
        return feature;
      });
      var info = document.getElementById('popup');
      if (feature) {
        var geometry = feature.getGeometry();
        var coord = geometry.getCoordinates();
        tooltip.setPosition(coord);
        $(element).siblings('.popover').css({ width: '250px' });
        $(element).siblings('.popover').css({ background: '#aaa' });
        $(info).popover({
          'placement': 'auto',
          'html': true,
          'content': feature.get('name')
        });
        $(info).popover('show');
      } else {
        // TODO : some warning with firebug here
        $(info).popover('destroy');
        $('.popover').remove();
      }
    };
    map.on('pointermove', function(evt) {
      if (evt.dragging) {
        return;
      }
      var pixel = map.getEventPixel(evt.originalEvent);
      displayFeatureInfo(pixel);
    });
    map.on('click', function(evt) {
      displayFeatureInfo(evt.pixel);
    });
  };
"""

# variables for alphabet_navigation()
_KEYPERSON, _KEYPLACE, _KEYEVENT, _ALPHAEVENT = 0, 1, 2, 3

COLLATE_LANG = glocale.collation

_NAME_STYLE_SHORT = 2
_NAME_STYLE_DEFAULT = 1
_NAME_STYLE_FIRST = 0
_NAME_STYLE_SPECIAL = None

PLUGMAN = BasePluginManager.get_instance()
CSS = PLUGMAN.process_plugin_data('WEBSTUFF')

#_NAME_COL = 3

_WRONGMEDIAPATH = []

_HTML_DBL_QUOTES = re.compile(r'([^"]*) " ([^"]*) " (.*)', re.VERBOSE)
_HTML_SNG_QUOTES = re.compile(r"([^']*) ' ([^']*) ' (.*)", re.VERBOSE)

# Events that are usually a family event
_EVENTMAP = set([EventType.MARRIAGE, EventType.MARR_ALT,
                 EventType.MARR_SETTL, EventType.MARR_LIC,
                 EventType.MARR_CONTR, EventType.MARR_BANNS,
                 EventType.ENGAGEMENT, EventType.DIVORCE,
                 EventType.DIV_FILING])

# Names for stylesheets
_NARRATIVESCREEN = "narrative-screen.css"
_NARRATIVEPRINT = "narrative-print.css"

def sort_people(dbase, handle_list, rlocale=glocale):
    """
    will sort the database people by surname
    """
    sname_sub = defaultdict(list)
    sortnames = {}

    for person_handle in handle_list:
        person = dbase.get_person_from_handle(person_handle)
        primary_name = person.get_primary_name()

        if primary_name.group_as:
            surname = primary_name.group_as
        else:
            group_map = _nd.primary_surname(primary_name)
            surname = dbase.get_name_group_mapping(group_map)

        # Treat people who have no name with those whose name is just
        # 'whitespace'
        if surname is None or surname.isspace():
            surname = ''
        sortnames[person_handle] = _nd.sort_string(primary_name)
        sname_sub[surname].append(person_handle)

    sorted_lists = []
    temp_list = sorted(sname_sub, key=rlocale.sort_key)

    for name in temp_list:
        if isinstance(name, bytes):
            name = name.decode('utf-8')
        slist = sorted(((sortnames[x], x) for x in sname_sub[name]),
                       key=lambda x: rlocale.sort_key(x[0]))
        entries = [x[1] for x in slist]
        sorted_lists.append((name, entries))

    return sorted_lists

def sort_event_types(dbase, event_types, event_handle_list, rlocale):
    """
    sort a list of event types and their associated event handles

    @param: dbase -- report database
    @param: event_types -- a dict of event types
    @param: event_handle_list -- all event handles in this database
    """
    event_dict = dict((evt_type, list()) for evt_type in event_types)

    for event_handle in event_handle_list:

        event = dbase.get_event_from_handle(event_handle)
        event_type = rlocale.translation.sgettext(event.get_type().xml_str())

        # add (gramps_id, date, handle) from this event
        if event_type in event_dict:
            sort_value = event.get_date_object().get_sort_value()
            event_dict[event_type].append((sort_value, event_handle))

    for tup_list in event_dict.values():
        tup_list.sort()

    # return a list of sorted tuples, one per event
    retval = [(event_type, event_list) for (event_type,
                                            event_list) in event_dict.items()]
    retval.sort(key=lambda item: str(item[0]))

    return retval

# Modified _get_regular_surname from WebCal.py to get prefix, first name,
# and suffix
def _get_short_name(gender, name):
    """ Will get suffix for all people passed through it """

    short_name = name.get_first_name()
    suffix = name.get_suffix()
    if suffix:
        # TODO for Arabic, should the next line's comma be translated?
        short_name = short_name + ", " + suffix
    return short_name

def __get_person_keyname(dbase, handle):
    """ .... """

    person = dbase.get_person_from_handle(handle)
    return _nd.sort_string(person.get_primary_name())

def __get_place_keyname(dbase, handle):
    """ ... """

    return utils.place_name(dbase, handle)

# See : http://www.gramps-project.org/bugs/view.php?id = 4423

# Contraction data taken from CLDR 22.1. Only the default variant is considered.
# The languages included below are, by no means, all the langauges that have
# contractions - just a sample of langauges that have been supported

# At the time of writing (Feb 2013), the following langauges have greater that
# 50% coverage of translation of Gramps: bg Bulgarian, ca Catalan, cs Czech, da
# Danish, de German, el Greek, en_GB, es Spanish, fi Finish, fr French, he
# Hebrew, hr Croation, hu Hungarian, it Italian, ja Japanese, lt Lithuanian, nb
# Noregian Bokmål, nn Norwegian Nynorsk, nl Dutch, pl Polish, pt_BR Portuguese
# (Brazil), pt_P Portugeuse (Portugal), ru Russian, sk Slovak, sl Slovenian, sv
# Swedish, vi Vietnamese, zh_CN Chinese.

# Key is the language (or language and country), Value is a list of
# contractions. Each contraction consists of a tuple. First element of the
# tuple is the list of characters, second element is the string to use as the
# index entry.

# The DUCET contractions (e.g. LATIN CAPIAL LETTER L, MIDDLE DOT) are ignored,
# as are the supresscontractions in some locales.

CONTRACTIONS_DICT = {
    # bg Bulgarian validSubLocales="bg_BG" no contractions
    # ca Catalan validSubLocales="ca_AD ca_ES"
    "ca" : [(("l·", "L·"), "L")],
    # Czech, validSubLocales="cs_CZ" Czech_Czech Republic
    "cs" : [(("ch", "cH", "Ch", "CH"), "CH")],
    # Danish validSubLocales="da_DK" Danish_Denmark
    "da" : [(("aa", "Aa", "AA"), "Å")],
    # de German validSubLocales="de_AT de_BE de_CH de_DE de_LI de_LU" no
    # contractions in standard collation.
    # el Greek validSubLocales="el_CY el_GR" no contractions.
    # es Spanish validSubLocales="es_419 es_AR es_BO es_CL es_CO es_CR es_CU
    # es_DO es_EA es_EC es_ES es_GQ es_GT es_HN es_IC es_MX es_NI es_PA es_PE
    # es_PH es_PR es_PY es_SV es_US es_UY es_VE" no contractions in standard
    # collation.
    # fi Finish validSubLocales="fi_FI" no contractions in default (phonebook)
    # collation.
    # fr French no collation data.
    # he Hebrew validSubLocales="he_IL" no contractions
    # hr Croation validSubLocales="hr_BA hr_HR"
    "hr" : [(("dž", "Dž"), "dž"),
            (("lj", "Lj", 'LJ'), "Ǉ"),
            (("Nj", "NJ", "nj"), "Ǌ")],
    # Hungarian hu_HU for two and three character contractions.
    "hu" : [(("cs", "Cs", "CS"), "CS"),
            (("dzs", "Dzs", "DZS"), "DZS"), # order is important
            (("dz", "Dz", "DZ"), "DZ"),
            (("gy", "Gy", "GY"), "GY"),
            (("ly", "Ly", "LY"), "LY"),
            (("ny", "Ny", "NY"), "NY"),
            (("sz", "Sz", "SZ"), "SZ"),
            (("ty", "Ty", "TY"), "TY"),
            (("zs", "Zs", "ZS"), "ZS")
           ],
    # it Italian no collation data.
    # ja Japanese unable to process the data as it is too complex.
    # lt Lithuanian no contractions.
    # Norwegian Bokmål
    "nb" : [(("aa", "Aa", "AA"), "Å")],
    # nn Norwegian Nynorsk validSubLocales="nn_NO"
    "nn" : [(("aa", "Aa", "AA"), "Å")],
    # nl Dutch no collation data.
    # pl Polish validSubLocales="pl_PL" no contractions
    # pt Portuguese no collation data.
    # ru Russian validSubLocales="ru_BY ru_KG ru_KZ ru_MD ru_RU ru_UA" no
    # contractions
    # Slovak,  validSubLocales="sk_SK" Slovak_Slovakia
    # having DZ in Slovak as a contraction was rejected in
    # http://unicode.org/cldr/trac/ticket/2968
    "sk" : [(("ch", "cH", "Ch", "CH"), "Ch")],
    # sl Slovenian validSubLocales="sl_SI" no contractions
    # sv Swedish validSubLocales="sv_AX sv_FI sv_SE" default collation is
    # "reformed" no contractions.
    # vi Vietnamese validSubLocales="vi_VN" no contractions.
    # zh Chinese validSubLocales="zh_Hans zh_Hans_CN zh_Hans_SG" no contractions
    # in Latin characters the others are too complex.
    }

    # The comment below from the glibc locale sv_SE in
    # localedata/locales/sv_SE :
    #
    # % The letter w is normally not present in the Swedish alphabet. It
    # % exists in some names in Swedish and foreign words, but is accounted
    # % for as a variant of 'v'.  Words and names with 'w' are in Swedish
    # % ordered alphabetically among the words and names with 'v'. If two
    # % words or names are only to be distinguished by 'v' or % 'w', 'v' is
    # % placed before 'w'.
    #
    # See : http://www.gramps-project.org/bugs/view.php?id = 2933
    #

# HOWEVER: the characters V and W in Swedish are not considered as a special
# case for several reasons. (1) The default collation for Swedish (called the
# 'reformed' collation type) regards the difference between 'v' and 'w' as a
# primary difference. (2) 'v' and 'w' in the 'standard' (non-default) collation
# type are not a contraction, just a case where the difference is secondary
# rather than primary. (3) There are plenty of other languages where a
# difference that is primary in other languages is secondary, and those are not
# specially handled.

def first_letter(string, rlocale=glocale):
    """
    Receives a string and returns the first letter
    """
    if string is None or len(string) < 1:
        return ' '

    norm_unicode = normalize('NFKC', str(string))
    contractions = CONTRACTIONS_DICT.get(COLLATE_LANG)
    if contractions is None:
        contractions = CONTRACTIONS_DICT.get(COLLATE_LANG.split("_")[0])

    if contractions is not None:
        for contraction in contractions:
            count = len(contraction[0][0])
            if (len(norm_unicode) >= count and
                    norm_unicode[:count] in contraction[0]):
                return contraction[1]

    # no special case
    return norm_unicode[0].upper()

try:
    import PyICU # pylint : disable=wrong-import-position
    PRIM_COLL = PyICU.Collator.createInstance(PyICU.Locale(COLLATE_LANG))
    PRIM_COLL.setStrength(PRIM_COLL.PRIMARY)

    def primary_difference(prev_key, new_key, rlocale=glocale):
        """
        Try to use the PyICU collation.
        """

        return PRIM_COLL.compare(prev_key, new_key) != 0

except:
    def primary_difference(prev_key, new_key, rlocale=glocale):
        """
        The PyICU collation is not available.

        Returns true if there is a primary difference between the two parameters
        See http://www.gramps-project.org/bugs/view.php?id=2933#c9317 if
        letter[i]+'a' < letter[i+1]+'b' and letter[i+1]+'a' < letter[i]+'b' is
        true then the letters should be grouped together

        The test characters here must not be any that are used in contractions.
        """

        return rlocale.sort_key(prev_key + "e") >= \
                   rlocale.sort_key(new_key + "f") or \
                   rlocale.sort_key(new_key + "e") >= \
                   rlocale.sort_key(prev_key + "f")

def get_first_letters(dbase, handle_list, key, rlocale=glocale):
    """
    get the first letters of the handle_list

    @param: handle_list -- One of a handle list for either person or
                           place handles or an evt types list
    @param: key         -- Either a person, place, or event type

    The first letter (or letters if there is a contraction) are extracted from
    all the objects in the handle list. There may be duplicates, and there may
    be letters where there is only a secondary or tertiary difference, not a
    primary difference. The list is sorted in collation order. For each group
    with secondary or tertiary differences, the first in collation sequence is
    retained. For example, assume the default collation sequence (DUCET) and
    names Ånström and Apple. These will sort in the order shown. Å and A have a
    secondary difference. If the first letter from these names was chosen then
    the inex entry would be Å. This is not desirable. Instead, the initial
    letters are extracted (Å and A). These are sorted, which gives A and Å. Then
    the first of these is used for the index entry.
    """
    index_list = []

    for handle in handle_list:
        if key == _KEYPERSON:
            keyname = __get_person_keyname(dbase, handle)

        elif key == _KEYPLACE:
            keyname = __get_place_keyname(dbase, handle)

        else:
            if rlocale != glocale:
                keyname = rlocale.translation.sgettext(handle)
            else:
                keyname = handle
        ltr = first_letter(keyname)

        index_list.append(ltr)

    # Now remove letters where there is not a primary difference
    index_list.sort(key=rlocale.sort_key)
    first = True
    prev_index = None
    for key in index_list[:]:   #iterate over a slice copy of the list
        if first or primary_difference(prev_index, key, rlocale):
            first = False
            prev_index = key
        else:
            index_list.remove(key)

    # return menu set letters for alphabet_navigation
    return index_list

def get_index_letter(letter, index_list, rlocale=glocale):
    """
    This finds the letter in the index_list that has no primary difference from
    the letter provided. See the discussion in get_first_letters above.
    Continuing the example, if letter is Å and index_list is A, then this would
    return A.
    """
    for index in index_list:
        if not primary_difference(letter, index, rlocale):
            return index

    LOG.warning("Initial letter '%s' not found in alphabetic navigation list",
                letter)
    LOG.debug("filtered sorted index list %s", index_list)
    return letter

def alphabet_navigation(index_list, rlocale=glocale):
    """
    Will create the alphabet navigation bar for classes IndividualListPage,
    SurnameListPage, PlaceListPage, and EventList

    @param: index_list -- a dictionary of either letters or words
    """
    sorted_set = defaultdict(int)

    for menu_item in index_list:
        sorted_set[menu_item] += 1

    # remove the number of each occurance of each letter
    sorted_alpha_index = sorted(sorted_set, key=rlocale.sort_key)

    # if no letters, return None to its callers
    if not sorted_alpha_index:
        return None

    num_ltrs = len(sorted_alpha_index)
    num_of_cols = 26
    num_of_rows = ((num_ltrs // num_of_cols) + 1)

    # begin alphabet navigation division
    with Html("div", id="alphanav") as alphabetnavigation:

        index = 0
        for row in range(num_of_rows):
            unordered = Html("ul")

            cols = 0
            while cols <= num_of_cols and index < num_ltrs:
                menu_item = sorted_alpha_index[index]
                if menu_item == ' ':
                    menu_item = '&nbsp;'
                # adding title to hyperlink menu for screen readers and
                # braille writers
                title_txt = "Alphabet Menu: %s" % menu_item
                title_str = rlocale.translation.sgettext(title_txt)
                hyper = Html("a", menu_item, title=title_str,
                             href="#%s" % menu_item)
                unordered.extend(Html("li", hyper, inline=True))

                index += 1
                cols += 1
            num_of_rows -= 1

            alphabetnavigation += unordered

    return alphabetnavigation

def _has_webpage_extension(url):
    """
    determine if a filename has an extension or not...

    @param: url -- filename to be checked
    """
    return any(url.endswith(ext) for ext in _WEB_EXT)

def add_birthdate(dbase, ppl_handle_list, rlocale):
    """
    This will sort a list of child handles in birth order
    For each entry in the list, we'll have :
         birth date
         The transtated birth date for the configured locale
         The transtated death date for the configured locale
         The handle for the child

    @param: dbase           -- The database to use
    @param: ppl_handle_list -- the handle for the people
    @param: rlocale         -- the locale for date translation
    """
    sortable_individuals = []
    for person_handle in ppl_handle_list:
        birth_date = 0    # dummy value in case none is found
        person = dbase.get_person_from_handle(person_handle)
        if person:
            birth_ref = person.get_birth_ref()
            birth1 = ""
            if birth_ref:
                birth = dbase.get_event_from_handle(birth_ref.ref)
                if birth:
                    birth1 = rlocale.get_date(birth.get_date_object())
                    birth_date = birth.get_date_object().get_sort_value()
            death_event = get_death_or_fallback(dbase, person)
            if death_event:
                death = rlocale.get_date(death_event.get_date_object())
            else:
                death = ""
        sortable_individuals.append((birth_date, birth1, death, person_handle))

    # return a list of handles with the individual's birthdate attached
    return sortable_individuals

def _find_birth_date(dbase, individual):
    """
    will look for a birth date within the person's events

    @param: dbase      -- The database to use
    @param: individual -- The individual for who we want to find the birth date
    """
    date_out = None
    birth_ref = individual.get_birth_ref()
    if birth_ref:
        birth = dbase.get_event_from_handle(birth_ref.ref)
        if birth:
            date_out = birth.get_date_object()
            date_out.fallback = False
    else:
        person_evt_ref_list = individual.get_primary_event_ref_list()
        if person_evt_ref_list:
            for evt_ref in person_evt_ref_list:
                event = dbase.get_event_from_handle(evt_ref.ref)
                if event:
                    if event.get_type().is_birth_fallback():
                        date_out = event.get_date_object()
                        date_out.fallback = True
                        LOG.debug("setting fallback to true for '%s'", event)
                        break
    return date_out

def _find_death_date(dbase, individual):
    """
    will look for a death date within a person's events

    @param: dbase      -- The database to use
    @param: individual -- The individual for who we want to find the death date
    """
    date_out = None
    death_ref = individual.get_death_ref()
    if death_ref:
        death = dbase.get_event_from_handle(death_ref.ref)
        if death:
            date_out = death.get_date_object()
            date_out.fallback = False
    else:
        person_evt_ref_list = individual.get_primary_event_ref_list()
        if person_evt_ref_list:
            for evt_ref in person_evt_ref_list:
                event = dbase.get_event_from_handle(evt_ref.ref)
                if event:
                    if event.get_type().is_death_fallback():
                        date_out = event.get_date_object()
                        date_out.fallback = True
                        LOG.debug("setting fallback to true for '%s'", event)
                        break
    return date_out

def build_event_data_by_individuals(dbase, ppl_handle_list):
    """
    creates a list of event handles and event types for this database

    @param: dbase           -- The database to use
    @param: ppl_handle_list -- the handle for the people
    """
    event_handle_list = []
    event_types = []

    for person_handle in ppl_handle_list:
        person = dbase.get_person_from_handle(person_handle)
        if person:

            evt_ref_list = person.get_event_ref_list()
            if evt_ref_list:
                for evt_ref in evt_ref_list:
                    event = dbase.get_event_from_handle(evt_ref.ref)
                    if event:

                        event_types.append(str(event.get_type()))
                        event_handle_list.append(evt_ref.ref)

            person_family_handle_list = person.get_family_handle_list()
            if person_family_handle_list:
                for family_handle in person_family_handle_list:
                    family = dbase.get_family_from_handle(family_handle)
                    if family:

                        family_evt_ref_list = family.get_event_ref_list()
                        if family_evt_ref_list:
                            for evt_ref in family_evt_ref_list:
                                event = dbase.get_event_from_handle(evt_ref.ref)
                                if event:
                                    event_types.append(str(event.type))
                                    event_handle_list.append(evt_ref.ref)

    # return event_handle_list and event types to its caller
    return event_handle_list, event_types

def name_to_md5(text):
    """This creates an MD5 hex string to be used as filename."""

    return md5(text.encode('utf-8')).hexdigest()

def get_gendex_data(database, event_ref):
    """
    Given an event, return the date and place a strings

    @param: database  -- The database
    @param: event_ref -- The event reference
    """
    doe = "" # date of event
    poe = "" # place of event
    if event_ref and event_ref.ref:
        event = database.get_event_from_handle(event_ref.ref)
        if event:
            date = event.get_date_object()
            doe = format_date(date)
            if event.get_place_handle():
                place_handle = event.get_place_handle()
                if place_handle:
                    place = database.get_place_from_handle(place_handle)
                    if place:
                        poe = _pd.display(database, place, date)
    return doe, poe

def format_date(date):
    """
    Format the date
    """
    start = date.get_start_date()
    if start != Date.EMPTY:
        cal = date.get_calendar()
        mod = date.get_modifier()
        quality = date.get_quality()
        if quality in DATE_QUALITY:
            qual_text = DATE_QUALITY[quality] + " "
        else:
            qual_text = ""
        if mod == Date.MOD_SPAN:
            val = "%sFROM %s TO %s" % (
                qual_text,
                make_gedcom_date(start, cal, mod, None),
                make_gedcom_date(date.get_stop_date(), cal, mod, None))
        elif mod == Date.MOD_RANGE:
            val = "%sBET %s AND %s" % (
                qual_text,
                make_gedcom_date(start, cal, mod, None),
                make_gedcom_date(date.get_stop_date(), cal, mod, None))
        else:
            val = make_gedcom_date(start, cal, mod, quality)
        return val
    return ""

# This command then defines the 'html_escape' option for escaping
# special characters for presentation in HTML based on the above list.
def html_escape(text):
    """Convert the text and replace some characters with a &# variant."""

    # First single characters, no quotes
    text = escape(text)

    # Deal with double quotes.
    match = _HTML_DBL_QUOTES.match(text)
    while match:
        text = "%s" "&#8220;" "%s" "&#8221;" "%s" % match.groups()
        match = _HTML_DBL_QUOTES.match(text)
    # Replace remaining double quotes.
    text = text.replace('"', '&#34;')

    # Deal with single quotes.
    text = text.replace("'s ", '&#8217;s ')
    match = _HTML_SNG_QUOTES.match(text)
    while match:
        text = "%s" "&#8216;" "%s" "&#8217;" "%s" % match.groups()
        match = _HTML_SNG_QUOTES.match(text)
    # Replace remaining single quotes.
    text = text.replace("'", '&#39;')

    return text
