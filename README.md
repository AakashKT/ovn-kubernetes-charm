# ovn-kubernetes-charm
<h3>Deploy the bundle</h3>
<pre>
cd bundles/kubernetes-ovn/
juju deploy bundle.yaml
</pre>
<b>Note:</b> Of course, you have to have juju bootstraped to a cloud env first. Have a look at https://jujucharms.com/docs/stable/getting-started
<br>

Steps to build the charm for Ubuntu Xenial:
<pre>
cd ~/Desktop
git clone https://github.com/AakashKT/ovn-kubernetes-charm.git

cd ovn-kubernetes-charm
source env-setup.sh

charm build ovn --series=xenial
</pre>

Deploy the bundle using the bundle/kubernetes-ovn/bundle.yaml file
