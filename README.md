# ovn-kubernetes-charm
This repo is a charm bundle to deploy Kubernetes with OVN

Steps to build the charm for Ubuntu Trusty:
<pre>
cd ~/Desktop
git clone https://github.com/AakashKT/ovn-kubernetes-charm.git

cd ovn-kubernetes-charm
source env-setup.sh

charm build ovn --series=xenial
</pre>

Deploy the bundle using the bundle/kubernetes-ovn/bundle.yaml file
