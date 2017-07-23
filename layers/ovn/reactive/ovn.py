import os
import json
import re
import sys
import subprocess
import time
import urllib.request as urllib2
import multiprocessing as mp

from charmhelpers.core import hookenv
from charmhelpers.core import host

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
    config = hookenv.config(key);
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

''' Common reactive handlers '''

@when_not('deps.installed')
def install_deps():
    hookenv.status_set('maintenance', 'Installing dependencies for OVN');

    conf = open('/tmp/ovn_conf', 'w+');
    conf.close();

    run_command('git clone https://github.com/openvswitch/ovn-kubernetes /tmp/ovn-kubernetes');
    os.chdir('/tmp/ovn-kubernetes');
    run_command('sudo -H pip2 install .');

    set_state('deps.installed');




''' Master reactive handlers '''

@when('master.initialised', 'master-config.worker.available')
def sign_and_send(master):
    cert_list = master.get_config('cert_to_sign');
    central_ip = get_my_ip();

    for cert in cert_list:
        os.chdir('/tmp/');
        cert_file = open('/tmp/ovncontroller-req.pem', 'w+');
        cert_file.write(cert);
        cert_file.close();
        run_command('sudo ovs-pki -d /certs/pki -b sign ovncontroller switch --force');

        cert_file = open('ovncontroller-cert.pem', 'r');
        signed_cert = cert_file.read();
        master.send_config({
            'signed_cert': signed_cert,
            'central_ip': central_ip
        });

@when('cni.is-master', 'master.initialised')
@when_not('gateway.installed')
def install_gateway(cni):
    hookenv.status_set('maintenance', 'Initialising gateway');

    run_command('sudo ovs-vsctl set Open_vSwitch . external_ids:k8s-api-server="0.0.0.0:8080"');

    run_command('git clone https://github.com/openvswitch/ovn-kubernetes /tmp/ovn-kubernetes');
    os.chdir('/tmp/ovn-kubernetes');
    run_command('sudo pip2 install .');

    old_interface = get_interface(old=True);
    new_interface = get_interface(old=False);

    op = run_command('ifconfig %s | grep "inet addr:"' % (new_interface));
    br_ip = op.lstrip().split()[1].replace('addr:', '');

    gateway_ip = run_command('ip route | grep default').split(' ')[2];
    hostname = run_command('hostname');

    op = run_command('ovn-k8s-overlay gateway-init \
                    --cluster-ip-subnet="192.168.0.0/16" \
                    --bridge-interface %s \
                    --physical-ip %s/32 \
                    --node-name="%s-gateway" \
                    --default-gw %s' % (new_interface, br_ip, hostname, gateway_ip));
    log('Gateway init output: %s' % (op));

    op = run_command('ovn-k8s-gateway-helper --physical-bridge=%s \
                        --physical-interface=%s --pidfile --detach' % (new_interface, old_interface));
    log('Gateway Helper start: %s' % (op));

    hookenv.status_set('active', 'Master subnet : 192.168.1.0/24');
    set_state('gateway.installed');

@when('cni.is-master', 'master.setup.done')
@when_not('master.initialised')
def initialise_master(cni):
    hookenv.status_set('maintenance', 'Initialising master network');

    central_ip = get_my_ip();
    hostname = run_command('hostname');

    run_command('sudo ovs-vsctl set Open_vSwitch . external_ids:k8s-api-server="0.0.0.0:8080"');
    run_command('sudo ovn-k8s-overlay master-init --cluster-ip-subnet="192.168.0.0/16" \
                    --master-switch-subnet="192.168.1.0/24" \
                    --node-name="%s"' % (hostname));

    run_command('sudo ovn-k8s-watcher --overlay --pidfile --log-file -vfile:info \
                    -vconsole:emer --detach');

    hookenv.status_set('maintenance', 'Waiting for gateway');
    set_state('master.initialised');

@when('cni.is-master', 'bridge.setup.done')
@when_not('master.setup.done')
def master_setup(cni):
    hookenv.status_set('maintenance', 'Setting up master');
    hookenv.open_ports(1, 2378);
    hookenv.open_ports(2380, 6442);
    hookenv.open_ports(6444, 65535);

    central_ip = get_my_ip();

    run_command('sudo /usr/share/openvswitch/scripts/ovn-ctl start_northd');
    run_command('sudo ovn-nbctl set-connection pssl:6641');
    run_command('sudo ovn-sbctl set-connection pssl:6642');

    os.chdir('/etc/openvswitch');
    run_command('sudo ovs-pki -d /certs/pki init --force');
    run_command('sudo cp /certs/pki/switchca/cacert.pem /etc/openvswitch/');
    run_command('sudo ovs-pki req ovnnb --force && sudo ovs-pki self-sign ovnnb --force');
    run_command('sudo ovn-nbctl set-ssl /etc/openvswitch/ovnnb-privkey.pem \
                    /etc/openvswitch/ovnnb-cert.pem  /certs/pki/switchca/cacert.pem');
    run_command('sudo ovs-pki req ovnsb --force && sudo ovs-pki self-sign ovnsb --force');
    run_command('sudo ovn-sbctl set-ssl /etc/openvswitch/ovnsb-privkey.pem \
                    /etc/openvswitch/ovnsb-cert.pem  /certs/pki/switchca/cacert.pem');

    run_command('sudo ovs-pki req ovncontroller');
    run_command('sudo ovs-pki -b -d /certs/pki sign ovncontroller switch --force');

    ovn_host_file = open('/etc/default/ovn-host', 'a');
    ovn_host_file.write('OVN_CTL_OPTS="--ovn-controller-ssl-key=/etc/openvswitch/ovncontroller-privkey.pem  \
        --ovn-controller-ssl-cert=/etc/openvswitch/ovncontroller-cert.pem \
        --ovn-controller-ssl-bootstrap-ca-cert=/etc/openvswitch/ovnsb-ca.cert"');
    ovn_host_file.close();

    run_command('sudo ovs-vsctl set Open_vSwitch . external_ids:ovn-remote="ssl:%s:6642" \
                    external_ids:ovn-nb="ssl:%s:6641" \
                    external_ids:ovn-encap-ip=%s \
                    external_ids:ovn-encap-type="%s"' % (central_ip, central_ip, central_ip, 'geneve'));
    run_command('sudo /usr/share/openvswitch/scripts/ovn-ctl \
                    --ovn-controller-ssl-key="/etc/openvswitch/ovncontroller-privkey.pem" \
                    --ovn-controller-ssl-cert="/etc/openvswitch/ovncontroller-cert.pem" \
                    --ovn-controller-ssl-bootstrap-ca-cert="/etc/openvswitch/ovnsb-ca.cert" \
                    restart_controller');

    set_state('master.setup.done');

@when('cni.is-master', 'deps.installed')
@when_not('bridge.setup.done')
def bridge_setup(cni):
    hookenv.status_set('maintenance', 'Setting up new interface');

    interface = get_config('gateway-physical-interface');
    if interface == 'none' or interface == None:
        op = run_command('ip route | grep default').split(' ');
        interface = op[4];

    store('old_interface', interface);
    store('new_interface', 'br%s' % (interface));

    op = run_command('ovn-k8s-util nics-to-bridge %s' % (interface));
    log('Bridge create output: %s' % (op));

    op = run_command('dhclient -r br%s' % (interface));
    op = run_command('dhclient br%s' % (interface));

    hookenv.status_set('maintenance', 'Waiting to initialise master');
    set_state('bridge.setup.done');


''' Worker reactive handlers '''

@when('cni.is-worker', 'master-config.master.available', 'worker.setup.done')
@when_not('worker.initialised')
def initialise_worker(cni, mconfig):
    hookenv.status_set('maintenance', 'Initialising worker network');

    local_ip = get_my_ip();
    central_ip = mconfig.get_config('central_ip')[0];
    hostname = run_command('hostname').replace('\n', '');

    run_command('ovs-vsctl set Open_vSwitch . \
                external_ids:k8s-api-server="%s:8080"' % (central_ip));
    run_command('ovn-k8s-overlay minion-init --cluster-ip-subnet="192.168.0.0/16" \
                    --minion-switch-subnet="192.168.2.0/24" --node-name="%s"' % (hostname));

    os.chdir('/tmp/');
    run_command('wget https://github.com/containernetworking/cni/releases/download/v0.5.2/cni-amd64-v0.5.2.tgz');
    run_command('sudo mkdir -p /opt/cni/bin');
    run_command('sudo mkdir -p /etc/cni/net.d');
    os.chdir('/opt/cni/bin/');
    run_command('sudo tar xvzf /tmp/cni-amd64-v0.5.2.tgz');

    hookenv.status_set('active', 'Worker subnet : 192.168.2.0/24');
    set_state('worker.initialised');

@when('cni.is-worker', 'master-config.master.available', 'worker.cert.registered',
            'worker.kv.setup')
@when_not('worker.setup.done')
def worker_setup(cni, mconfig):
    hookenv.status_set('maintenance', 'Setting up worker');
    hookenv.open_ports(1, 79);
    hookenv.open_ports(81, 442);
    hookenv.open_ports(444, 65535);
    central_ip = mconfig.get_config('central_ip')[0];
    local_ip = get_my_ip();

    run_command('sudo ovs-vsctl set Open_vSwitch . \
                    external_ids:ovn-remote="ssl:%s:6642" \
                    external_ids:ovn-nb="ssl:%s:6641" \
                    external_ids:ovn-encap-ip=%s \
                    external_ids:ovn-encap-type=%s' % (central_ip, central_ip, local_ip, 'geneve'));
    
    ovn_host_file = open('/etc/default/ovn-host', 'a');
    ovn_host_file.write('OVN_CTL_OPTS="--ovn-controller-ssl-key=/etc/openvswitch/ovncontroller-privkey.pem  \
                    --ovn-controller-ssl-cert=/etc/openvswitch/ovncontroller-cert.pem \
                    --ovn-controller-ssl-bootstrap-ca-cert=/etc/openvswitch/ovnsb-ca.cert"');
    ovn_host_file.close();

    run_command('sudo /usr/share/openvswitch/scripts/ovn-ctl \
                    --ovn-controller-ssl-key="/etc/openvswitch/ovncontroller-privkey.pem" \
                    --ovn-controller-ssl-cert="/etc/openvswitch/ovncontroller-cert.pem" \
                    --ovn-controller-ssl-bootstrap-ca-cert="/etc/openvswitch/ovnsb-ca.cert" \
                    restart_controller');
    set_state('worker.setup.done');

@when('cni.is-worker', 'master-config.master.available')
@when_not('worker.cert.registered')
def receive_cert(cni, mconfig):
    hookenv.status_set('maintenance', 'Certificate received')

    cert_list = mconfig.get_config('signed_cert')[0];
    master_ip = mconfig.get_config('central_ip')[0];
    cni.set_config(cidr='192.168.0.0/16');

    for cert in cert_list:
        os.chdir('/etc/openvswitch');
        cert_file = open('/etc/openvswitch/ovncontroller-cert.pem', 'a');
        cert_file.write(cert);
        cert_file.close();

    set_state('worker.cert.registered');

@when('cni.is-worker', 'master-config.connected')
@when_not('worker.cert.sent')
def send_cert(cni, mconfig):
    os.chdir('/etc/openvswitch');
    run_command('sudo ovs-pki req ovncontroller');

    req_file = open('ovncontroller-req.pem', 'r');
    cert = req_file.read();
    mconfig.send_config({
        'cert_to_sign': cert
    });

    hookenv.status_set('maintenance', 'Waiting for certificate');
    set_state('worker.cert.sent');

@when_not('worker.kv.setup')
def setup_kv():
    interface = get_config('gateway-physical-interface');
    if interface == 'none' or interface == None:
        op = run_command('ip route | grep default').split(' ');
        interface = op[4];

    store('new_interface', interface);
    set_state('worker.kv.setup');


#########################################################################
# Helper functions
#########################################################################


def get_my_ip():
    interface = get_interface(old=False);

    op = run_command('ifconfig %s | grep "inet addr:"' % (interface));
    br_ip = op.lstrip().split()[1].replace('addr:', '');

    return br_ip;

def get_interface(old):
    key = 'old_interface' if old == True else 'new_interface';
    return retrieve(key);
