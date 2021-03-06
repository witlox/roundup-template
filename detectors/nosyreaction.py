from roundup.anypy.sets_ import set

from roundup import roundupdb, hyperdb

def nosyreaction(db, cl, nodeid, oldvalues):
    ''' A standard detector is provided that watches for additions to the
        "messages" property.

        When a new message is added, the detector sends it to all the users on
        the "nosy" list for the issue that are not already on the "recipients"
        list of the message.

        Those users are then appended to the "recipients" property on the
        message, so multiple copies of a message are never sent to the same
        user.

        The journal recorded by the hyperdatabase on the "recipients" property
        then provides a log of when the message was sent to whom.
    '''
    # send a copy of all new messages to the nosy list
    log = db.get_logger().getChild('nosyreaction')
    messages = determineNewMessages(cl, nodeid, oldvalues)
    issue = db.issue.getnode(nodeid)
    spamstatus = db.status.lookup('spam')
    for msgid in messages:
        try:
            if issue.status != spamstatus:
                quiet = db.msg.get(msgid, 'quiet')
                if quiet:
                    # Need to update the recipients of the
                    # message. cl.nosymessage() will only send
                    # messages to people who are not member of the
                    # msg.recipients attribute...
                    msgrecipients = [i for i in issue.nosy if 'Operator' not in db.user.get(i, 'roles').split(',')]
                    newcontent = '=== Internal message - this message was only sent to Roundup Operators ===\n\n' + db.msg.get(msgid, 'content')
                    db.msg.set(msgid, recipients=msgrecipients, content=newcontent)
                    log.info("Sending INTERNAL message for issue %s with update message %s", nodeid, msgid)

                    cl.nosymessage(nodeid, msgid, oldvalues)
                else:
                    log.info("Sending message for issue %s with update message %s", nodeid, msgid)
                    cl.nosymessage(nodeid, msgid, oldvalues)
        except roundupdb.MessageSendError, message:
            log.error("Error while sending nosy reaction for msg id %s: %s", msgid, message)
            raise roundupdb.DetectorError, message

    # If the issue was updated without an update message, `messages`
    # is empty.
    if not messages and oldvalues:
        try:
            # If assignee(s) have been updated, send the message
            # around.
            if issue.assignee != oldvalues['assignee'] or \
               issue.status != oldvalues.get('status', ''):
                if issue.status != spamstatus:
                    # Only send message if it's not spam
                    log.info("Sending message for issue %s", nodeid)
                    cl.nosymessage(nodeid, None, oldvalues)
        except roundupdb.MessageSendError, message:
            log.error("Error while sending messages for issue %s without update message: %s", nodeid, message)
            raise roundupdb.DetectorError, message

def determineNewMessages(cl, nodeid, oldvalues):
    ''' Figure a list of the messages that are being added to the given
        node in this transaction.
    '''
    messages = []
    if oldvalues is None:
        # the action was a create, so use all the messages in the create
        messages = cl.get(nodeid, 'messages')
    elif oldvalues.has_key('messages'):
        # the action was a set (so adding new messages to an existing issue)
        m = {}
        for msgid in oldvalues['messages']:
            m[msgid] = 1
        messages = []
        # figure which of the messages now on the issue weren't there before
        for msgid in cl.get(nodeid, 'messages'):
            if not m.has_key(msgid):
                messages.append(msgid)
    return messages

def updatenosy(db, cl, nodeid, newvalues):
    '''Update the nosy list for changes to the assignee
    '''
    # nodeid will be None if this is a new node
    current_nosy = set()
    if nodeid is None:
        ok = ('new', 'yes')
    else:
        ok = ('yes',)
        # old node, get the current values from the node if they haven't
        # changed
        if not newvalues.has_key('nosy'):
            nosy = cl.get(nodeid, 'nosy')
            for value in nosy:
                current_nosy.add(value)

    # if the nosy list changed in this transaction, init from the new value
    if newvalues.has_key('nosy'):
        nosy = newvalues.get('nosy', [])
        for value in nosy:
            if not db.hasnode('user', value):
                continue
            current_nosy.add(value)

    new_nosy = set(current_nosy)

    # add assignee(s) to the nosy list
    if newvalues.has_key('assignee') and newvalues['assignee'] is not None:
        propdef = cl.getprops()
        if isinstance(propdef['assignee'], hyperdb.Link):
            assignee_ids = [newvalues['assignee']]
        elif isinstance(propdef['assignee'], hyperdb.Multilink):
            assignee_ids = newvalues['assignee']
        for assignee_id in assignee_ids:
            new_nosy.add(assignee_id)

    # see if there's any new messages - if so, possibly add the author and
    # recipient to the nosy
    if newvalues.has_key('messages'):
        if nodeid is None:
            ok = ('new', 'yes')
            messages = newvalues['messages']
        else:
            ok = ('yes',)
            # figure which of the messages now on the issue weren't
            oldmessages = cl.get(nodeid, 'messages')
            messages = []
            for msgid in newvalues['messages']:
                if msgid not in oldmessages:
                    messages.append(msgid)

        # configs for nosy modifications
        add_author = getattr(db.config, 'ADD_AUTHOR_TO_NOSY', 'new')
        add_recips = getattr(db.config, 'ADD_RECIPIENTS_TO_NOSY', 'new')

        # now for each new message:
        msg = db.msg
        for msgid in messages:
            if add_author in ok:
                authid = msg.get(msgid, 'author')
                new_nosy.add(authid)

            # add on the recipients of the message
            if add_recips in ok:
                for recipient in msg.get(msgid, 'recipients'):
                    new_nosy.add(recipient)

    if current_nosy != new_nosy:
        # that's it, save off the new nosy list
        newvalues['nosy'] = list(new_nosy)

def init(db):
    db.issue.react('create', nosyreaction)
    db.issue.react('set', nosyreaction)
    db.issue.audit('create', updatenosy)
    db.issue.audit('set', updatenosy)
