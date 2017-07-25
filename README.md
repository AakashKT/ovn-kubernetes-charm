# ovn-kubernetes-charm
<h3>Deploy the bundle</h3>
<pre>
cd bundles/kubernetes-ovn/
juju deploy bundle.yaml

Steps to build the charm for Ubuntu Xenial:
<pre>
cd ~/Desktop
git clone https://github.com/AakashKT/ovn-kubernetes-charm.git

cd ovn-kubernetes-charm
source env-setup.sh

charm build ovn --series=xenial
</pre>

Deploy the bundle using the bundle/kubernetes-ovn/bundle.yaml file
