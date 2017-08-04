import os
import json
import re
import sys
import subprocess
import time
import urllib.request as urllib2
import multiprocessing as mp

from charmhelpers.core import host

from charmhelpers.core.hookenv import (
    is_leader,
    open_port,
    status_set,
    leader_set,
    leader_get,
    config,
    unit_public_ip,
    unit_private_ip,
)

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

from charms.reactive.helpers import (
    mark_invoked,
    was_invoked,
)

from charms.reactive import (
    when,
    when_not,
    when_file_changed,
    hook,
    RelationBase,
    scopes,
    set_state,
    remove_state
)


CONF_FILE = '/tmp';


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

def get_config(key):
    config = config(key);
    return config;

def retrieve(key):
    try:
        conf = open('/tmp/ovn_conf', 'r');
    except:
        return '';

    plain_text = conf.read();
    conf.close();
    if plain_text == '':
        return '';
    else:
        data = json.loads(plain_text);
        return data[key];

def store(key, value):
    conf = open('/tmp/ovn_conf', 'r');
    plain_text = conf.read();
    conf.close();

    conf = open('/tmp/ovn_conf', 'w+');

    data = {};
    if plain_text != '':
        data = json.loads(plain_text);
    data[key] = value;

    conf.truncate(0);
    conf.seek(0, 0);
    conf.write(json.dumps(data));
    conf.close();
    

#########################################################################
# Hooks and reactive handlers
#########################################################################

@hook('install')
def install_dependencies():
    status_set('maintenance', 'Installing dependencies for OVS');

    run_command('sudo apt-get update ; sudo apt-get upgrade ; sudo apt-get install git -y');

    run_command('sudo apt-get install -y build-essential fakeroot debhelper \
                    autoconf automake bzip2 libssl-dev docker.io \
                    openssl graphviz python-all procps \
                    python-dev python-setuptools python-pip python3 python3.4 \
                    python-twisted-conch libtool git dh-autoreconf \
                    linux-headers-$(uname -r) libcap-ng-dev');
    run_command('sudo pip2 install six');
    

@when_not('openvswitch.installed')
def install_openvswitch():
    status_set('maintenance', 'Configure and make openvswitch');

    run_command('git clone https://github.com/openvswitch/ovs.git /tmp/ovs');

    os.chdir('/tmp/ovs');

    run_command('./boot.sh');
    run_command('./configure --prefix=/usr --localstatedir=/var  --sysconfdir=/etc \
                        --enable-ssl --with-linux=/lib/modules/`uname -r`/build');
    run_command('make -j3 ; sudo make install ; sudo make modules_install');

    status_set('maintenance', 'Replacing kernel module');

    run_command('sudo mkdir /etc/depmod.d/');
    run_command('for module in datapath/linux/*.ko; \
                    do modname="$(basename ${module})" ; \
                    echo "override ${modname%.ko} * extra" >> "/etc/depmod.d/openvswitch.conf" ; \
                    echo "override ${modname%.ko} * weak-updates" >> "/etc/depmod.d/openvswitch.conf" ; \
                    done');
    run_command('/sbin/modprobe openvswitch');

    run_command('/usr/share/openvswitch/scripts/ovs-ctl start --system-id=$(uuidgen)');

    status_set('maintenance', 'Open vSwitch Installed');
    set_state('openvswitch.installed')

