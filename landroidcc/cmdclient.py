import argparse
import logging
import time

from landroidcc import Landroid

logging.basicConfig(format='%(asctime)s %(module)-8s %(funcName)-10s %(levelname)-8s %(message)s',
                    level=logging.INFO,
                    datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Communicate with cloud based Worx landroid mowers.')
    parser.add_argument('username',
                        help='Username for cloud access (same as for landroid app)')
    parser.add_argument('password',
                        help='Password for cloud access (same as for landroid app)')
    parser.add_argument('--verbose', '--debug', action="store_true", help="Provide Verbose/Debug output")
    parser.add_argument('--silent', action="store_true", help="Only show errors and warnings, but no info")
    parser.add_argument('--status', action="store_true", help="Show actual status one time")
    parser.add_argument('--statusRaw', action="store_true", help="Show actual status one time")
    parser.add_argument('--startMowing', action="store_true", help="Send 'start' command to mower")
    parser.add_argument('--pauseMowing', action="store_true", help="Send 'pause' command to mower")
    parser.add_argument('--goHome', action="store_true", help="Send 'home' command to mower")
    parser.add_argument('--watchPassive', action="store_true", help="Just connects and waits for status updates")

    args = parser.parse_args()
    if args.verbose:
        log.setLevel(logging.DEBUG)
        logging.getLogger("urllib3").setLevel(logging.DEBUG)
    elif args.silent:
        log.setLevel(logging.WARN)
        logging.getLogger("urllib3").setLevel(logging.WARN)
    else:
        log.setLevel(logging.INFO)
        logging.getLogger("urllib3").setLevel(logging.INFO)

    if any([args.status, args.statusRaw, args.startMowing, args.pauseMowing, args.goHome,
            args.watchPassive]):
        mower = Landroid()
        mower.connect(args.username, args.password)
        if args.status or args.statusRaw:
            status = mower.get_status()
        if args.status:
            print(mower)
            print(status)
        if args.statusRaw:
            print("Raw status: ")
            print(status.raw)
        if args.startMowing:
            mower.start_mowing()
        elif args.pauseMowing:
            mower.stop_mowing()
        elif args.goHome:
            mower.go_home()
        elif args.watchPassive:
            def statusUpdate(status):
                print (status)
            mower.set_statuscallback(statusUpdate)
            while True:
                log.info("Watching for status updates. Hit ctrl-c to stop")
                time.sleep(60)


if __name__ == '__main__':
    main()
