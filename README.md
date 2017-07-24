# ovn-kubernetes-charm
<h3>Deploy the bundle</h3>
cd bundles/kubernetes-ovn/
juju deploy bundle.yaml
<hr>
<b>Note:</b> Get the value for config option in OVN, "gateway-physical-interface" by running the following on your machine:
<pre>
ip route | grep default
Output : default via 192.168.0.1 dev <b>wlp1s0</b>  proto static  metric 600
</pre>
Choose the highlighted word.<br>
<b>Note:</b> For now, please run the following commands once done deploying. These commands are to be run on the worker node.
<pre>
sudo cp /root/cdk/ca.crt /etc/openvswitch/k8s-ca.crt
K8S_API_SERVER_IP="<master_node_name>:6443"
API_TOKEN="<some_token>"
sudo ovs-vsctl set Open_vSwitch .   external_ids:k8s-api-server="https://$K8S_API_SERVER_IP" external_ids:k8s-api-token="$API_TOKEN"

sudo ovn-k8s-watcher --overlay --pidfile --log-file -vfile:info \
                    -vconsole:emer --detach
sudo ovn-k8s-gateway-helper --physical-bridge=<gateway-physical-interface> \
                        --physical-interface=br<gateway-physical-interface> --pidfile --detach
</pre>
This repo is a charm bundle to deploy Kubernetes with OVN

Steps to build the charm for Ubuntu Xenial:
<pre>
cd ~/Desktop
git clone https://github.com/AakashKT/ovn-kubernetes-charm.git

cd ovn-kubernetes-charm
source env-setup.sh

charm build ovn --series=xenial
</pre>

Deploy the bundle using the bundle/kubernetes-ovn/bundle.yaml file
