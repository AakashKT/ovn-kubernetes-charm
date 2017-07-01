import os

from charmhelpers.core import hookenv
from charms.reactive import hook, RelationBase, scopes

class OvnCentralRequires(RelationBase):

	scope = scopes.UNIT;

	@hook("{requires:ovn-central-config}-relation-{joined,changed}")
	def changed_joined(self):
		conv = self.conversation();
		if conv.get_remote('central_ip'):
			conv.set_state("{relation_name}.available");


	@hook("{requires:ovn-central-config}-relation-{departed}")
	def departed(self):
		conv = self.conversation();
		conv.remove_state("{relation_name}.available");


	def get_config(self, key):
		conv = self.conversation();
		value = conv.get_remote(key);

		return value;
