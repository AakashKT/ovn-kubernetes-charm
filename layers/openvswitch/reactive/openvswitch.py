import os
import json
import re
import sys
import subprocess
import time
import urllib.request as urllib2

from charmhelpers.core.host import (
    service_start,
    service_stop,
    log,
    mkdir,
    write_file,
)

from charmhelpers.fetch import (
    apt_install,
    apt_update,
    apt_upgrade
)

from charms.reactive import (
    when, 
    when_not, 
    hook, 
    set_state
)


#########################################################################
# Common functions
#########################################################################

def run_command(command=None):

    if command is None:
        return False;

    log('Running Command "%s"' % command);
    try:
        return subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT).decode('utf-8').replace('\n', '');
    except subprocess.CalledProcessError as e:
        log('Error running "%s" : %s' % (command, e.output));

        return False;

def get_my_ip():
    return json.loads(urllib2.urlopen('https://api.ipify.org/?format=json').read().decode('utf-8'))['ip'];


#########################################################################
# Hooks and reactive handlers
#########################################################################

@hook('install')
def install_dependencies():

    run_command('sudo apt-get update ; sudo apt-get upgrade ; sudo apt-get install git -y');

    run_command('sudo apt-get install -y build-essential fakeroot debhelper \
                    autoconf automake bzip2 libssl-dev \
                    openssl graphviz python-all procps \
                    python-dev python-setuptools python-pip python3 python3.4 \
                    python-twisted-conch libtool git dh-autoreconf \
                    linux-headers-$(uname -r) libcap-ng-dev');
    run_command('sudo pip2 install six');
    

@when_not('openvswitch.installed')
def install_openvswitch():

    run_command('git clone https://github.com/openvswitch/ovs.git /tmp/ovs');

    os.chdir('/tmp/ovs');

    run_command('./boot.sh');
    run_command('./configure --prefix=/usr --localstatedir=/var  --sysconfdir=/etc \
                        --enable-ssl --with-linux=/lib/modules/`uname -r`/build');
    run_command('make -j3 ; sudo make install ; sudo make modules_install');

    run_command('sudo mkdir /etc/depmod.d/');
    run_command('for module in datapath/linux/*.ko; \
                    do modname="$(basename ${module})" ; \
                    echo "override ${modname%.ko} * extra" >> "/etc/depmod.d/openvswitch.conf" ; \
                    echo "override ${modname%.ko} * weak-updates" >> "/etc/depmod.d/openvswitch.conf" ; \
                    done');
    run_command('/sbin/modprobe openvswitch');

    run_command('/usr/share/openvswitch/scripts/ovs-ctl start --system-id=$(uuidgen)');

    set_state('openvswitch.installed')

