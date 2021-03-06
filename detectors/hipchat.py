#!/usr/bin/env python
# -*- coding: utf-8 -*-#
#
#
# Copyright (C) 2015, S3IT, University of Zurich. All rights reserved.
#
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
"""
This reactor will notify an HipChat room every time an issue is created or modified.

Configuration is needed for this detector, in `detectors/config.ini`:

[hipchat]
base_url = <base url of hipchat api>
room = <room>
token = <token>

"""

__docformat__ = 'reStructuredText'
__author__ = 'Antonio Messina <antonio.s.messina@gmail.com>'

import os
import urllib2
import json

from ConfigParser import RawConfigParser

def notify_hipchat(db, msg, color=None):
    log = db.get_logger().getChild('hipchat')
    try:
        cfg = db.config.detectors
        base_url = cfg['HIPCHAT_BASE_URL']
        room = cfg['HIPCHAT_ROOM']
        token = cfg['HIPCHAT_TOKEN']
    except Exception as ex:
        log.error("Config options not found. Check detectors/config.ini for hipchat options")
        return

    try:
        url = "%s/%s/notification?auth_token=%s" % (base_url, room, token)
        data = {'message': msg,
                'notify': True}
        if color is not None:
            data['color'] = color
        fmtdata = json.dumps(data)
        headers = {"Content-Type": "application/json"}
        request = urllib2.Request(url, data=fmtdata, headers=headers)

        log.debug("Sending message to %s" % url)
        response = urllib2.urlopen(request, fmtdata)
        response.close()

    except Exception as ex:
        log.warning("Unable to send message to hipchat. Message was :%s, error: %s", msg, ex)


def newissue(db, cl, nodeid, oldvalues):
    issue = db.issue.getnode(nodeid)

    msg = """NEW <a href="{0}issue{1}">issue{1}</a> has been created by {2}.
"<i>{3}</i>" """.format(db.config.TRACKER_WEB,
              nodeid,
              db.user.get(issue.creator, 'username'),
              issue.title)

    notify_hipchat(db, msg, color='red')


def issueupdate(db, cl, nodeid, oldvalues):
    issue = db.issue.getnode(nodeid)
    allmsg = []

    color = None
    if db.status.get(issue.status, 'name') == 'solved':
        color = 'green'
    elif db.status.get(issue.status, 'name') == 'new':
        color = 'red'

    actor = db.user.get(issue.actor, 'username')
    actorname = db.user.get(issue.actor, 'realname')

    if issue.title != oldvalues['title']:
        allmsg.append('title: "<i>%s</i>" -> "<i>%s</i>"' % (oldvalues['title'], issue.title))

    if issue.assignee != oldvalues['assignee']:
        if oldvalues['assignee']:
            olduid = db.user.get(oldvalues['assignee'], 'username')
            oldname = db.user.get(oldvalues['assignee'], 'realname')
            old = '%s (%s)' % (olduid, oldname)
        else:
            old = 'None'

        if issue.assignee:
            newuid = db.user.get(issue.assignee, 'username')
            newname = db.user.get(issue.assignee, 'realname')
            new = '%s (%s)' % (newuid, newname)
        else:
            new = 'None'
        allmsg.append("%s (%s) changed assignee: %s -> %s" % (actor, actorname, old, new))

    if issue.status != oldvalues['status']:
        old = db.status.get(oldvalues['status'], 'name')
        new = db.status.get(issue.status, 'name')
        allmsg.append("%s (%s) changed status: %s -> %s" % (actor, actorname, old, new))

    if issue.messages != oldvalues['messages']:
        msgid = issue.messages[-1]
        msg = db.msg.getnode(msgid)
        creator = db.user.get(msg.creator, 'username')
        creatorname = db.user.get(msg.creator, 'realname')
        allmsg.append("followup message from %s (%s)" % (creator, creatorname))

    if issue.topics != oldvalues['topics']:
        old = [db.topic.get(topicid, 'name') for topicid in oldvalues['topics']]
        new = [db.topic.get(topicid, 'name') for topicid in issue.topics]
        allmsg.append("%s (%s) changed topics: %s -> %s" % (actor, actorname, str.join(', ', old), str.join(', ', new)))

    if issue.nosy != oldvalues['nosy']:
        old = [db.user.get(userid, 'username') for userid in oldvalues['nosy']]
        new = [db.user.get(userid, 'username') for userid in issue.nosy]
        allmsg.append("%s (%s) changed subscribers: %s -> %s" % (actor, actorname, str.join(', ', old), str.join(', ', new)))

    # Actually send notification, if needed.
    if allmsg:
        # Prepend link to the issue
        issuelink = """<a href="{0}issue{1}">issue{1} ({2})</a>: """.format(db.config.TRACKER_WEB, nodeid, issue.title)
        # add "newlines"
        text = str.join('<br />', [issuelink + msg for msg in allmsg])
        notify_hipchat(db, text, color=color)

def init(db):
    db.issue.react('create', newissue)
    db.issue.react('set', issueupdate)
