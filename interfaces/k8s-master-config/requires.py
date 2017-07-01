import os

from charmhelpers.core import hookenv
from charms.reactive import hook, RelationBase, scopes

class K8SMasterRequires(RelationBase):

	scope = scopes.UNIT;

	@hook("{requires:k8s-master-config}-relation-{joined,changed}")
	def changed_joined(self):
		conv = self.conversation();
		if conv.get_remote('k8s_api_ip'):
			conv.set_state("{relation_name}.available");


	@hook("{requires:k8s-master-config}-relation-{departed}")
	def departed(self):
		conv = self.conversation();
		conv.remove_state("{relation_name}.available");


	def get_config(self, key):
		conv = self.conversation();
		value = conv.get_remote(key);

		return value;
