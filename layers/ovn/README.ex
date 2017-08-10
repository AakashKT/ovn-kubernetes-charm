# Overview

This charm provides an SDN via the use of OVN and can be used with any principal charm implementing the [kubernetes-cni](https://github.com/juju-solutions/interface-kubernetes-cni) interface.

# Usage

This charm is subordinate.

<code>
juju deploy ovn
juju deploy kubernetes-master
juju deploy kubernetes-worker
juju add-relation ovn kubernetes-master
juju add-relation ovn kubernetes-worker
</code>

# Configuration

The "gateway-physical-interface" option will allow you to choose an interface on which to create the gateway bridge. If unsure, leave it to "none" to use the default interface.


