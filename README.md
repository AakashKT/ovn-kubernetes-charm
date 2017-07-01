# ovn-kubernetes-charm
This repo is a charm bundle to deploy Kubernetes with OVN

Steps to build the charm for Ubuntu Trusty:
<pre>
cd ~/Desktop
git clone https://github.com/AakashKT/ovn-kubernetes-charm.git

cd ovn-kubernetes-charm
source env-setup.sh

charm build ovn-central
charm build k8s-master
charm build k8s-minion
charm build k8s-gateway
</pre>
<br>
Charms :
<ul>
<li>ovn-central</li>
<li>k8s-master</li>
<li>k8s-minion</li>
<li>k8s-gateway</li>
</ul>
<br>
Relations :
<ul>
<li>ovn-central --- k8s-master</li>
<li>ovn-central --- k8s-minion</li>
<li>ovn-central --- k8s-gateway</li>
<li>k8s-master --- k8s-gateway</li>
<li>k8s-master --- k8s-minion</li>
</ul>
