import os
from charms.reactive import when, when_not, set_state

import json
try:
    import urllib.request as urllib2
except ImportError:
    import urllib2

@when_not('k8s-minion.installed')
@when('onetime-setup.done')
def install_k8s_minion():
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

    os.system('ovs-vsctl set Open_vSwitch . external_ids:k8s-api-server="$(cat /tmp/central_ip):8080" ');

    os.system("git clone https://github.com/openvswitch/ovn-kubernetes /tmp/ovn-kubernetes");
    os.chdir("/tmp/ovn-kubernetes");
    os.system("sudo pip2 install .");
    os.system("ovn-k8s-overlay minion-init --cluster-ip-subnet='192.168.0.0/16' --master-switch-subnet='192.168.2.0/24' --node-name='kube-minion1' ")

    set_state('k8s-minion.installed')


@when('ovn-central-comms.available')
@when_not('onetime-setup.done')
def onetime_setup(ovn_obj):
    central_ip = ovn_obj.get_central_ip();
    local_ip = json.loads(urllib2.urlopen('https://api.ipify.org/?format=json').read().decode("utf-8"))["ip"];

    f = open("/tmp/central_ip", "w");
    f.write(central_ip);
    f.close();

    command = ("ovs-vsctl set Open_vSwitch . external_ids:ovn-remote='tcp:" + str(central_ip) + ":6642' "
               "external_ids:ovn-nb='tcp:" + str(central_ip) + ":6641' "
               "external_ids:ovn-encap-ip=" + str(local_ip) + " "
               "external_ids:ovn-encap-type='stt'" 
                );
    os.system(command);
    os.system("ovs-vsctl set Open_vSwitch . external_ids:system-id=$(uuidgen)");
    os.system("/usr/share/openvswitch/scripts/ovn-ctl start_controller");

    set_state("onetime-setup.done");