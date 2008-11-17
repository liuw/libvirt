#!/usr/bin/python -u
import sys,getopt,os
import libvirt
import select

mypoll = select.poll()
TIMEOUT_MS = 1000

# handle globals
h_fd       = 0
h_events   = 0
h_cb       = None
h_opaque   = None

# timeout globals
t_active   = 0
t_timeout  = -1
t_cb       = None
t_opaque   = None

#####################################################
# Callback Functions
#####################################################
def eventToString(event):
    eventStrings = ( "Added",
                     "Removed",
                     "Started",
                     "Suspended",
                     "Resumed",
                     "Stopped",
                     "Saved",
                     "Restored" );
    return eventStrings[event];

def myDomainEventCallback1 (conn, dom, event, detail, opaque):
    print "myDomainEventCallback1 EVENT: Domain %s(%s) %s %d" % (dom.name(), dom.ID(), eventToString(event), detail)

def myDomainEventCallback2 (conn, dom, event, detail, opaque):
    print "myDomainEventCallback2 EVENT: Domain %s(%s) %s %d" % (dom.name(), dom.ID(), eventToString(event), detail)

#####################################################
# EventImpl Functions
#####################################################
def myEventHandleTypeToPollEvent(events):
    ret = 0
    if events & libvirt.VIR_EVENT_HANDLE_READABLE:
        ret |= select.POLLIN
    if events & libvirt.VIR_EVENT_HANDLE_WRITABLE:
        ret |= select.POLLOUT
    if events & libvirt.VIR_EVENT_HANDLE_ERROR:
        ret |= select.POLLERR;
    if events & libvirt.VIR_EVENT_HANDLE_HANGUP:
        ret |= select.POLLHUP;
    return ret

def myPollEventToEventHandleType(events):
    ret = 0;
    if events & select.POLLIN:
        ret |= libvirt.VIR_EVENT_HANDLE_READABLE;
    if events & select.POLLOUT:
        ret |= libvirt.VIR_EVENT_HANDLE_WRITABLE;
    if events & select.POLLERR:
        ret |= libvirt.VIR_EVENT_HANDLE_ERROR;
    if events & select.POLLHUP:
        ret |= libvirt.VIR_EVENT_HANDLE_HANGUP;
    return ret;

def myAddHandle(fd, events, cb, opaque):
    global h_fd, h_events, h_cb, h_opaque
    #print "Adding Handle %s %s %s %s" % (str(fd), str(events), str(cb), str(opaque))
    h_fd = fd
    h_events = events
    h_cb = cb
    h_opaque = opaque

    mypoll.register(fd, myEventHandleTypeToPollEvent(events))

def myUpdateHandle(fd, event):
    global h_fd, h_events
    #print "Updating Handle %s %s" % (str(fd), str(events))
    h_fd = fd
    h_events = event
    mypoll.unregister(fd)
    mypoll.register(fd, myEventHandleTypeToPollEvent(event))

def myRemoveHandle(fd):
    global h_fd
    #print "Removing Handle %s" % str(fd)
    h_fd = 0
    mypoll.unregister(fd)

def myAddTimeout(timeout, cb, opaque):
    global t_active, t_timeout, t_cb, t_opaque
    #print "Adding Timeout %s %s %s" % (str(timeout), str(cb), str(opaque))
    t_active = 1;
    t_timeout = timeout;
    t_cb = cb;
    t_opaque = opaque;

def myUpdateTimeout(timer, timeout):
    global t_timeout
    #print "Updating Timeout %s" % (str(timer), str(timeout))
    t_timeout = timeout;

def myRemoveTimeout(timer):
    global t_active
    #print "Removing Timeout %s" % str(timer)
    t_active = 0;

##########################################
# Main
##########################################

def usage():
        print "usage: "+os.path.basename(sys.argv[0])+" [uri]"
        print "   uri will default to qemu:///system"

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h", ["help"] )
    except getopt.GetoptError, err:
        # print help information and exit:
        print str(err) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()

    if len(sys.argv) > 1:
        uri = sys.argv[1]
    else:
        uri = "qemu:///system"

    print "Using uri:" + uri

    libvirt.virEventRegisterImpl( myAddHandle,
                               myUpdateHandle,
                               myRemoveHandle,
                               myAddTimeout,
                               myUpdateTimeout,
                               myRemoveTimeout );
    vc = libvirt.open(uri)

    #Add 2 callbacks to prove this works with more than just one
    vc.domainEventRegister(myDomainEventCallback1,None)
    vc.domainEventRegister(myDomainEventCallback2,None)

    while 1:
        try:
            sts = mypoll.poll(TIMEOUT_MS)
        except select.error, err:
            if err[0] == errno.EINTR:
                    continue
            raise
        except KeyboardInterrupt:
            print "Keyboard Interrupt caught - exiting cleanly"
            break

        if not sts:
            #print "Timed out"
            continue

        rfd = sts[0][0]
        revents = sts[0][1]

        if t_active:
            #print "Invoking Timeout CB"
            t_cb(t_timeout, t_opaque[0], t_opaque[1])

        if revents & select.POLLHUP:
            print "Reset by peer";
            return -1;

        if h_cb != None:
            #print "Invoking Handle CB"
            h_cb(h_fd, myPollEventToEventHandleType(revents & h_events),
                 h_opaque[0], h_opaque[1])

        #print "DEBUG EXIT"
        #break

if __name__ == "__main__":
    main()

