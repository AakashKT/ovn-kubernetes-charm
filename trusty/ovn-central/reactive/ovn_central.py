import os
from charms.reactive import when, when_not, hook, set_state

import json
try:
    import urllib.request as urllib2
except ImportError:
    import urllib2

@when_not('ovn-central.installed')
def install_ovn_central():
    # Do your setup here.
    #
    # If your charm has other dependencies before it can install,
    # add those as @when() clauses above., or as additional @when()
    # decorated handlers below
    #
    # See the following for information about reactive charms:
    #
    #  * https://jujucharms.com/docs/devel/developer-getting-started
    #  * https://github.com/juju-solutions/layer-basic#overview
    #


    os.system("/usr/share/openvswitch/scripts/ovn-ctl start_northd");

    os.system("ovn-nbctl set-connection ptcp:6641");
    os.system("ovn-sbctl set-connection ptcp:6642");

    set_state('ovn-central.installed')


@when("ovn-central-comms.available")
@when("ovn-central.installed")
def broadcast_and_setup(ovn_obj):

    central_ip = json.loads(urllib2.urlopen('https://api.ipify.org/?format=json').read().decode("utf-8"))["ip"];

    command = ("ovs-vsctl set Open_vSwitch . external_ids:ovn-remote='tcp:" + str(central_ip) + ":6642' "
               "external_ids:ovn-nb='tcp:" + str(central_ip) + ":6641' "
               "external_ids:ovn-encap-ip=" + str(central_ip) + " "
               "external_ids:ovn-encap-type='stt'" 
                );
    os.system(command);
    os.system("ovs-vsctl set Open_vSwitch . external_ids:system-id=$(uuidgen)");
    os.system("/usr/share/openvswitch/scripts/ovn-ctl start_controller");

    ovn_obj.send_ip(central_ip);

    set_state("onetime-setup.done");

