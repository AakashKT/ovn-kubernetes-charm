import os

from charmhelpers.core import hookenv
from charms.reactive import hook, RelationBase, scopes

class K8SMasterProvides(RelationBase):

	scope = scopes.GLOBAL;

	@hook("{provides:k8s-master-config}-relation-{joined,changed}")
	def changed_joined(self):
		self.set_state("{relation_name}.available");


	@hook("{provides:k8s-master-config}-relation-{departed}")
	def departed(self):
		self.remove_state("{relation_name}.available");


	def send_config(self, config):
		self.set_remote(data=config);
