#!/bin/bash
#
#	/etc/rc.d/init.d/web2pyd
#
# Starts the Web2py Daemon on Fedora (Red Had Linux)
#
# To execute automatically at startup
#
#    sudo chkconfig --add web2pyd
#
# chkconfig: 2345 90 10
# description: Web2py Daemon
# processname: web2pyd
# pidfile: /var/lock/subsys/web2pyd

source /etc/rc.d/init.d/functions

RETVAL=0
NAME=web2pyd
DESC="Web2py Daemon"
DAEMON_DIR="/usr/lib/web2py"
ADMINPASS="admin"
#ADMINPASS="<recycle>"
PIDFILE=/var/run/$NAME.pid
PORT=8001

cd $DAEMON_DIR

start() {
    echo -n $"Starting $DESC ($NAME): "
    daemon --check $NAME python $DAEMON_DIR/web2py.py -a $ADMINPASS -d $PIDFILE -P -p $PORT &
    #RETVAL=$?
    RETVAL=0
    if [ $RETVAL -eq 0 ]; then
    	touch /var/lock/subsys/$NAME
    fi
    echo
}	

obtainpid() {
    pidstr=`pgrep $NAME`
    pidcount=`awk -v name="$pidstr" 'BEGIN{split(name,a," "); print length(a)}'`
    if [ ! -r "$PIDFILE" ] && [ $pidcount -ge 2 ]; then	
        pid=`awk -v name="$pidstr" 'BEGIN{split(name,a," "); print a[1]}'`
        echo $NAME is already running and it was not started by the init script.
    fi
}

stop() {
    echo -n $"Shutting down $DESC ($NAME): "
    if [ -r "$PIDFILE" ]; then
        pid=`cat $PIDFILE`
        kill -s 3 $pid
        RETVAL=$?
    else
        RETVAL=1
    fi
    [ $RETVAL -eq 0 ] && success || failure
    echo
    if [ $RETVAL -eq 0 ]; then
        rm -f /var/lock/subsys/$NAME
        rm -f $PIDFILE
    fi
    return $RETVAL
}

restart() {
	stop
	start
}

forcestop() {
   echo -n $"Shutting down $DESC ($NAME): "

   kill -s 3 $pid 
   RETVAL=$?
   [ $RETVAL -eq 0 ] && success || failure
   echo
   if [ $RETVAL -eq 0 ]; then
     rm -f /var/lock/subsys/$NAME
     rm -f $PIDFILE
   fi

   return $RETVAL
}

status() {
    if [ -r "$PIDFILE" ]; then
        pid=`cat $PIDFILE`
    fi
    if [ $pid ]; then
        echo "$NAME (pid $pid) is running..."
    else
        echo "$NAME is stopped"
    fi
}

case "$1" in
    start)
	start
	;;
    stop)
	stop
	;;
    status)
    status
	;;
    restart)
    restart
    RETVAL=$?
	;;
    reload)
	;;
    condrestart)
    [ -e /var/lock/subsys/$NAME ] && restart	
    RETVAL=$?
	;;
    *)
    echo $"Usage: $0 {start|stop|forcestop|restart|condrestart|status}"
    RETVAL=1
	;;
esac

exit $RETVAL

