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


#########################################################################
# Common functions
#########################################################################

def run_command(command=None):

    if command is None:
        return False;

    log('Running Command "%s"' % command);
    try:
        return subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT).decode('utf-8');
    except subprocess.CalledProcessError as e:
        log('Error running "%s" : %s' % (command, e.output));

        return False;

def get_my_ip():
    return json.loads(urllib2.urlopen('https://api.ipify.org/?format=json').read().decode('utf-8'))['ip'];


#########################################################################
# Hooks and reactive handlers
#########################################################################

@when('master.installed')
@when_not('ovn.installed')
def gateway_master():
    install_ovn(True);

@when('worker.installed')
@when_not('ovn.installed')
def gateway_worker():
    install_ovn(False);

@when('master.installed', 'master-config.ip_request')
def send_ident(master):
    central_ip = get_my_ip();

    config = {
        'central_ip' : central_ip,
    };
    master.send_config(config);


@when('cni.is-worker', 'master-config.connected')
@when_not('cert.sent')
def send_cert(cni, worker):
    os.chdir('/etc/openvswitch');
    run_command('sudo ovs-pki req ovncontroller');

    req_file = open('ovncontroller-req.pem', 'r');
    cert = req_file.read();
    worker.send_config({
        'cert_to_sign': cert
    });

    hookenv.status_set('maintenance', 'Waiting for cert');
    set_state('cert.sent');

@when('cni.is-worker', 'master-config.master.available')
@when_not('worker.cert.registered')
def receive_data(cni, worker):
    cert_list = worker.get_config('signed_cert');
    master_ip = worker.get_config('central_ip')[0];

    for cert in cert_list:
        os.chdir('/etc/openvswitch');
        cert_file = open('/etc/openvswitch/ovncontroller-cert.pem', 'a');
        cert_file.write(cert);
        cert_file.close();

    hookenv.status_set('maintenance', 'Cert received');
    set_state('worker.cert.registered');

    install_worker(master_ip);


@when('master.installed', 'master-config.worker.available')
def sign_and_send(master):
    cert_list = master.get_config('cert_to_sign');
    central_ip = get_my_ip();

    for cert in cert_list:
        os.chdir('/tmp/');
        cert_file = open('/tmp/ovncontroller-req.pem', 'a');
        cert_file.write(cert);
        cert_file.close();
        run_command('sudo ovs-pki -d /certs/pki -b sign ovncontroller switch');

        cert_file = open('ovncontroller-cert.pem', 'r');
        signed_cert = cert_file.read();
        master.send_config({
            'signed_cert': signed_cert,
            'central_ip': central_ip
        });


@when('cni.is-master')
@when_not('master.installed')
def install_master(cni):
    hookenv.status_set('maintenance', 'Initialising master network');

    hookenv.open_port(6641);
    hookenv.open_port(6642);
    hookenv.open_port(8080);

    central_ip = get_my_ip();
    hostname = run_command('hostname').replace('\n', '');

    run_command('sudo /usr/share/openvswitch/scripts/ovn-ctl start_northd');

    os.chdir('/etc/openvswitch');
    run_command('sudo ovs-pki -d /certs/pki init --force');
    run_command('sudo cp /certs/pki/switchca/cacert.pem /etc/openvswitch/');
    run_command('sudo ovs-pki req ovnnb && sudo ovs-pki self-sign ovnnb');
    run_command('sudo ovn-nbctl set-ssl /etc/openvswitch/ovnnb-privkey.pem \
                    /etc/openvswitch/ovnnb-cert.pem  /certs/pki/switchca/cacert.pem');
    run_command('sudo ovs-pki req ovnsb && sudo ovs-pki self-sign ovnsb');
    run_command('sudo ovn-sbctl set-ssl /etc/openvswitch/ovnsb-privkey.pem \
                    /etc/openvswitch/ovnsb-cert.pem  /certs/pki/switchca/cacert.pem');

    run_command('sudo ovs-pki req ovncontroller');
    run_command('sudo ovs-pki -b -d /certs/pki sign ovncontroller switch');

    ovn_host_file = open('/etc/default/ovn-host', 'a');
    ovn_host_file.write('OVN_CTL_OPTS="--ovn-controller-ssl-key=/etc/openvswitch/ovncontroller-privkey.pem  \
        --ovn-controller-ssl-cert=/etc/openvswitch/ovncontroller-cert.pem \
        --ovn-controller-ssl-bootstrap-ca-cert=/etc/openvswitch/ovnsb-ca.cert"');
    ovn_host_file.close();

    run_command('sudo ovn-nbctl set-connection pssl:6641');
    run_command('sudo ovn-sbctl set-connection pssl:6642');

    run_command('sudo ovs-vsctl set Open_vSwitch . external_ids:ovn-remote="ssl:%s:6642" \
                    external_ids:ovn-nb="ssl:%s:6641" \
                    external_ids:ovn-encap-ip=%s \
                    external_ids:ovn-encap-type="%s"' % (central_ip, central_ip, central_ip, 'geneve'));

    run_command('sudo /usr/share/openvswitch/scripts/ovn-ctl \
                    --ovn-controller-ssl-key="/etc/openvswitch/ovncontroller-privkey.pem" \
                    --ovn-controller-ssl-cert="/etc/openvswitch/ovncontroller-cert.pem" \
                    --ovn-controller-ssl-bootstrap-ca-cert="/etc/openvswitch/ovnsb-ca.cert" \
                    restart_controller');
    run_command('sudo ovs-vsctl set Open_vSwitch . external_ids:k8s-api-server="0.0.0.0:8080"');

    run_command('git clone https://github.com/openvswitch/ovn-kubernetes /tmp/ovn-kubernetes');
    os.chdir('/tmp/ovn-kubernetes');
    run_command('sudo -H pip2 install .');
    run_command('sudo ovn-k8s-overlay master-init --cluster-ip-subnet="192.168.0.0/16" \
                    --master-switch-subnet="192.168.1.0/24" \
                    --node-name="%s"' % (hostname));

    run_command('sudo ovn-k8s-watcher --overlay --pidfile --log-file -vfile:info \
                    -vconsole:emer --detach');

    hookenv.status_set('maintenance', 'Waiting for gateway');
    set_state('master.installed');


#########################################################################
# Helper functions
#########################################################################

def install_worker(central_ip):
    hookenv.status_set('maintenance', 'Initialising worker network');
    hookenv.open_port(8080);

    config = hookenv.config();
    local_ip = get_my_ip();
    hostname = run_command('hostname').replace('\n', '');

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

    run_command('ovs-vsctl set Open_vSwitch . \
                external_ids:k8s-api-server="%s:8080"' % (central_ip));

    run_command('git clone https://github.com/openvswitch/ovn-kubernetes /tmp/ovn-kubernetes');
    os.chdir('/tmp/ovn-kubernetes');
    run_command('sudo -H pip2 install .');
    run_command('ovn-k8s-overlay minion-init --cluster-ip-subnet="192.168.0.0/16" \
                    --minion-switch-subnet="192.168.2.0/24" --node-name="%s"' % (hostname));

    os.chdir('/tmp/');
    run_command('wget https://github.com/containernetworking/cni/releases/download/v0.5.2/cni-amd64-v0.5.2.tgz');
    run_command('sudo mkdir -p /opt/cni/bin');
    run_command('sudo mkdir -p /etc/cni/net.d');
    os.chdir('/opt/cni/bin/');
    run_command('sudo tar xvzf /tmp/cni-amd64-v0.5.2.tgz');

    hookenv.status_set('maintenance', 'Waiting for gateway');
    set_state('worker.installed');


def install_ovn(is_master):
    config = hookenv.config();

    run_command('git clone https://github.com/openvswitch/ovn-kubernetes /tmp/ovn-kubernetes');
    os.chdir('/tmp/ovn-kubernetes');
    run_command('sudo pip2 install .');

    interface = config['gateway-physical-interface'];
    if(interface == 'none'):
        interface = run_command('ip route get 8.8.8.8 | awk "{ print $5; exit }"').replace('\n', '');

    op = run_command('ovn-k8s-util nics-to-bridge %s' % (interface));
    log('Bridge create output :');
    log(op);

    op = run_command('dhclient -r br%s' % (interface));
    log('Release interface : %s' % (op));
    op = run_command('dhclient br%s' % (interface));
    log('Fresh assign : %s' % (op));

    op = run_command('ifconfig br%s | grep "inet addr:"' % (interface));
    br_ip = op.lstrip().split()[1].replace('addr:', '');

    gateway_ip = run_command('ip route | grep default').replace('\n', '').split(' ')[2];
    hostname = run_command('hostname').replace('\n', '');

    op = run_command('ovn-k8s-overlay gateway-init \
                    --cluster-ip-subnet="192.168.0.0/16" \
                    --bridge-interface br%s \
                    --physical-ip %s/32 \
                    --node-name="%s-gateway" \
                    --default-gw %s' % (interface, br_ip, hostname, gateway_ip));
    log('Gateway init output :');
    log(op);

    op = run_command('ovn-k8s-gateway-helper --physical-bridge=br%s \
                        --physical-interface=%s --pidfile --detach' % (interface, interface));
    log('Daemon start : %s' % (op));

    if is_master:
        hookenv.status_set('active', 'Master subnet : 192.168.1.0/24');
    else:
        hookenv.status_set('active', 'Worker subnet : 192.168.2.0/24');
    set_state('ovn.installed')