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
    open_port,
    open_ports,
    status_set,
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
    conf = config(key);
    return conf;

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
# Relation Class
#########################################################################

class MasterConfigPeer(RelationBase):

    scope = scopes.UNIT;

    @hook("{peers:master-config}-relation-{joined}")
    def joined(self):
        conv = self.conversation();
        conv.set_state("{relation_name}.connected");

    @hook("{peers:master-config}-relation-{changed}")
    def changed(self):
        conv = self.conversation();
        worker_id = conv.get_local(key='worker_id');

        if worker_id != None and conv.get_remote(worker_id):
            conv.set_state("{relation_name}.master.data.available");
        elif conv.get_remote('cert_to_sign'):
            conv.set_state("{relation_name}.worker.cert.available");

    @hook("{peers:master-config}-relation-{departed}")
    def departed(self):
        conv = self.conversation();

        conv.remove_state("{relation_name}.connected");
        conv.remove_state("{relation_name}.master.data.available");
        conv.remove_state("{relation_name}.worker.cert.available");

    def set_worker_id(self, worker_id):
        convs = self.conversations();

        for conv in convs:
            conv.set_local(key='worker_id', value=worker_id);

    def get_worker_data(self):
        convs = self.conversations();

        final_data = [];
        for conv in convs:
            worker_unit = {};

            cert = conv.get_remote('cert_to_sign');
            worker_hostname = conv.get_remote('worker_hostname');

            worker_unit['cert_to_sign'] = cert;
            worker_unit['worker_hostname'] = worker_hostname;

            final_data.append(worker_unit);

        return final_data;

    def send_worker_data(self, data):
        convs = self.conversations();

        for conv in convs:
            conv.set_remote(data=data);


    def send_signed_certs(self, certs):
        convs = self.conversations();
        for conv in convs:
            for key, value in certs.items():
                data_str = json.dumps(value);
                conv.set_remote(key=key, value=data_str);

    def get_signed_cert(self, worker_hostname):
        convs = self.conversations();
        
        final = None;
        for conv in convs:
            data = conv.get_remote(worker_hostname);

            if data != '' and data != None:
                data = json.loads(data);
                final = data;
                break;

        return final;