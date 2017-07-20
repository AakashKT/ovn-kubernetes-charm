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

@when('k8s-config.available')
def send_ip(master):
    master_ip = get_my_ip();

    master.send_config({
        'master_ip': master_ip
    });

@when('cni.connected')
@when_not('cni.configured')
def configure_cni(cni):
    ''' Set master configuration on the CNI relation. This lets the CNI
    subordinate know that we're the master so it can respond accordingly. '''
    cni.set_config(is_master=True, kubeconfig_path='')


@when('kubernetes-master.installed')
@when_not('services.started')
def start_master_services():
    hookenv.status_set('maintenance', 'Starting master');
    hookenv.open_port(8080);

    run_command('sudo docker run --net=host \
                    -d gcr.io/google_containers/etcd:2.0.12 /usr/local/bin/etcd \
                    --addr=127.0.0.1:4001 --bind-addr=0.0.0.0:4001 --data-dir=/var/etcd/data');
    
    k8s_processes = open('/tmp/k8s.sh', 'w+');
    k8s_processes.write('#!/bin/bash/\n \
                            nohup sudo /tmp/k8s/server/kubernetes/server/bin/kube-apiserver \
                                --service-cluster-ip-range=192.168.200.0/24 \
                                --address=0.0.0.0 \
                                --etcd-servers=http://127.0.0.1:4001 \
                                --v=2 2>&1 0<&- &>/dev/null & \n \
                            nohup sudo /tmp/k8s/server/kubernetes/server/bin/kube-controller-manager \
                                --master=127.0.0.1:8080 \
                                --v=2 2>&1 0<&- &>/dev/null & \n \
                            nohup sudo /tmp/k8s/server/kubernetes/server/bin/kube-scheduler \
                                --master=127.0.0.1:8080 \
                                --v=2 2>&1 0<&- &>/dev/null & \n');
    k8s_processes.close();
    run_command('bash /tmp/k8s.sh');

    hookenv.status_set('maintenance', 'Kubernetes master running');
    set_state('services.started');


@when_not('kubernetes-master.installed')
def install_kubernetes_master():
    hookenv.status_set('maintenance', 'Installing kubernetes');
    channel = '1.5/stable';

    run_command('sudo apt-get install -y docker.io');

    run_command('mkdir /tmp/k8s/');
    os.chdir('/tmp/k8s/');

    run_command('wget https://github.com/kubernetes/kubernetes/releases/download/v1.5.3/kubernetes.tar.gz');
    run_command('tar xvzf kubernetes.tar.gz');
    run_command('echo "yes" | ./kubernetes/cluster/get-kube-binaries.sh');

    run_command('mkdir /tmp/k8s/server/');
    os.chdir('/tmp/k8s/server');
    run_command('tar xvzf ../kubernetes/server/kubernetes-server-linux-amd64.tar.gz');

    run_command('sudo cp /tmp/k8s/server/kubernetes/server/bin/kubectl /usr/local/bin');

    hookenv.status_set('maintenance', 'Waiting to start master');
    set_state('kubernetes-master.installed')