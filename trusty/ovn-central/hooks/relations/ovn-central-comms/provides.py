import os
from charmhelpers.core import hookenv
from charms.reactive import hook, RelationBase, scopes

class OvnCentralProvides(RelationBase):

	scope = scopes.GLOBAL;

	@hook("{provides:ovn-central-comms}-relation-{joined,changed}")
	def changed_joined(self):
		self.set_state("{relation_name}.available");


	@hook("{provides:ovn-central-comms}-relation-{departed}")
	def departed(self):
		self.remove_state("{relation_name}.available");


	def send_ip(self, central_ip):

		data = {
			"central_ip" : central_ip,
		};

		self.set_remote(**data);
