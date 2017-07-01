import os

from charmhelpers.core import hookenv
from charms.reactive import hook, RelationBase, scopes

class OvnCentralProvides(RelationBase):

	scope = scopes.GLOBAL;

	@hook("{provides:ovn-central-config}-relation-{joined,changed}")
	def changed_joined(self):
		self.set_state("{relation_name}.available");


	@hook("{provides:ovn-central-config}-relation-{departed}")
	def departed(self):
		self.remove_state("{relation_name}.available");

	def send_config(self, config):
		self.set_remote(data=config);
