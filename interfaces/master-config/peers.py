import os

from charmhelpers.core import hookenv
from charms.reactive import hook, RelationBase, scopes

class MasterConfigPeer(RelationBase):

	scope = scopes.UNIT;

	@hook("{peers:master-config}-relation-{joined}")
	def joined(self):
		conv = self.conversation();
		conv.set_state("{relation_name}.connected");

	@hook("{peers:master-config}-relation-{changed}")
	def changed(self):
		conv = self.conversation();
		if conv.get_remote('central_ip'):
			conv.set_state("{relation_name}.master.data.available");
		elif conv.get_remote('cert_to_sign'):
			conv.set_state("{relation_name}.worker.cert.available");

	@hook("{peers:master-config}-relation-{departed}")
	def departed(self):
		conv = self.conversation();

		conv.remove_state("{relation_name}.connected");
		conv.remove_state("{relation_name}.master.ip.available");
		conv.remove_state("{relation_name}.worker.cert.available");

	def send_config(self, config):
		conv = self.conversation();
		conv.set_remote(data=config);

	def get_config(self, key):
		conv = self.conversation();
		return conv.get_remote(key);
