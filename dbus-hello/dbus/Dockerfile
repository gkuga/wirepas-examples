FROM alpine:3.23

RUN apk add --no-cache dbus

# dbus-daemon resolves each client's UID to a user name to match it against the
# policy below. A client whose UID does not exist here is refused, so this user
# must exist in the bus container even though nothing runs as it.
RUN adduser --disabled-password --uid 1000 wirepas

COPY com.wirepas.sink.conf /etc/dbus-1/system.d/

# dbus-daemon refuses to start if a stale pid file is left behind.
CMD rm -f /run/dbus/dbus.pid && exec dbus-daemon --system --nofork --print-address
