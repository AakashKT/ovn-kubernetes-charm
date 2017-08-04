import os

from charmhelpers.core import hookenv
from charms.reactive import hook, RelationBase, scopes

class K8SConfigRequires(RelationBase):

    scope = scopes.UNIT;

    @hook("{requires:k8s-config}-relation-{joined,changed}")
    def changed_joined(self):
        conv = self.conversation();
        if conv.get_remote('master_ip'):
            conv.set_state("{relation_name}.available");


    @hook("{requires:k8s-config}-relation-{departed}")
    def departed(self):
        conv = self.conversation();
        conv.remove_state("{relation_name}.available");


    def get_config(self, key):
        conv = self.conversation();
        value = conv.get_remote(key);

        return value;