import os

from charmhelpers.core import hookenv
from charms.reactive import hook, RelationBase, scopes

class OvnCentralRequires(RelationBase):

	scope = scopes.UNIT;

	@hook("{requires:ovn-central-comms}-relation-{joined,changed}")
	def changed_joined(self):
		conversation = self.conversation();

		if conversation.get_remote("central_ip"):
			conversation.set_state("{relation_name}.available");


	@hook("{requires:ovn-central-comms}-relation-{departed}")
	def departed(self):

		conversation = self.conversation();
		conversation.remove_state("{relation_name}.available");


	def get_central_ip(self):
		conv = self.conversation();
		central_ip = conv.get_remote("central_ip");
		
		return central_ip;