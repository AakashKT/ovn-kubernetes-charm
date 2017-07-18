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


@when('cni.connected')
@when_not('cni.configured')
def configure_cni(cni):
    ''' Set master configuration on the CNI relation. This lets the CNI
    subordinate know that we're the master so it can respond accordingly. '''
    cni.set_config(is_master=False, kubeconfig_path='')


@when('k8s-config.available', 'kubernetes-worker.installed')
@when_not('services.installed')
def start_worker_services(worker):
    hookenv.status_set('maintenance', 'Starting worker');
    master_ip = worker.get_config('master_ip');

    k8s_processes = open('/tmp/k8s.sh', 'w+');
    k8s_processes.write('!#/bin/bash\n \
                            nohup sudo /tmp/k8s/server/kubernetes/server/bin/kubelet \
                                --api-servers=http://%s:8080 \
                                --enable-server=true \
                                --network-plugin=cni \
                                --cni-conf-dir=/etc/cni/net.d \
                                --cni-bin-dir="/opt/cni/bin/" \
                                --v=2 2>&1 0<&- &>/dev/null &' % (master_ip));
    k8s_processes.close();
    run_command('bash /tmp/k8s.sh');

    hookenv.status_set('maintenance', 'Kubernetes worker running');
    set_state('services.installed');


@when_not('kubernetes-worker.installed')
def install_kubernetes_worker():
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

    os.chdir('/tmp/');
    run_command('wget https://github.com/containernetworking/cni/releases/download/v0.5.2/cni-amd64-v0.5.2.tgz');
    run_command('sudo mkdir -p /opt/cni/bin');
    run_command('sudo mkdir -p /etc/cni/net.d/');
    os.chdir('/opt/cni/bin/');
    run_command('sudo tar xvzf ~/cni-amd64-v0.5.2.tgz');

    hookenv.status_set('maintenance', 'Waiting for worker to start');
    set_state('kubernetes-worker.installed')
