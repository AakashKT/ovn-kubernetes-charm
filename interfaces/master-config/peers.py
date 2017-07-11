import os

from charmhelpers.core import hookenv
from charms.reactive import hook, RelationBase, scopes

class MasterConfigPeer(RelationBase):

	scope = scopes.GLOBAL;

	@hook("{peers:master-config}-relation-{joined}")
	def joined(self):
		conv = self.conversation();
		conv.set_state("{relation_name}.connected");

	@hook("{peers:master-config}-relation-{changed}")
	def changed(self):
		conv = self.conversation();
		if conv.get_remote('central_ip'):
			conv.set_state("{relation_name}.available");

	@hook("{peers:master-config}-relation-{departed}")
	def departed(self):
		conv = self.conversation();
		conv.remove_state("{relation_name}.available");

	def send_config(self, config):
		conv = self.conversation();
		conv.set_remote(data=config);

	def get_config(self, key):
		conv = self.conversation();
		value = conv.get_remote(key);

		return value;