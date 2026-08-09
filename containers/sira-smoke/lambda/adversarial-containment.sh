#!/bin/sh
set -eu

# Gate L2 only. The container supervisor, not this fixture, owns the lifecycle.
# The same single container verifies its required applets before it spawns any
# adversarial process. It then ignores TERM, creates a new session, reparents a
# grandchild, and keeps attempting to consume the finite container PID budget.
applets=$(/bin/busybox --list)
for required in sh setsid sleep ps kill; do
  case "
$applets
" in
    *"
$required
"*) ;;
    *)
      printf 'T07_APPLET_MISSING=%s\n' "$required"
      exit 72
      ;;
  esac
done
printf 'T07_APPLETS_VERIFIED=sh,setsid,sleep,ps,kill\n'
printf 'T07_FIXTURE_ROOT_PID=%s\n' "$$"
trap '' TERM

(
  trap '' TERM
  /bin/busybox setsid /bin/sh -c '
    trap "" TERM
    (
      trap "" TERM
      while :; do
        set +e
        /bin/busybox sleep 3600 &
        spawn_status=$?
        set -e
        if [ "$spawn_status" -ne 0 ]; then
          printf "T07_PID_LIMIT_OBSERVED=grandchild-spawner\n"
          while :; do :; done
        fi
        /bin/busybox sleep 0.02 || true
      done
    ) &
    while :; do /bin/busybox sleep 3600; done
  ' &
) &

while :; do
  set +e
  (
    trap '' TERM
    /bin/busybox sleep 3600
  ) &
  spawn_status=$?
  set -e
  if [ "$spawn_status" -ne 0 ]; then
    printf 'T07_PID_LIMIT_OBSERVED=root-spawner\n'
    while :; do :; done
  fi
  /bin/busybox sleep 0.02 || true
done
