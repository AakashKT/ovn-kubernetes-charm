import os
from charms.reactive import when, when_not, hook, set_state

@hook('install')
def install_dependencies():

    os.system("sudo apt-get update ; sudo apt-get upgrade ; sudo apt-get install git -y");

    os.system("sudo apt-get install -y build-essential fakeroot debhelper \
                    autoconf automake bzip2 libssl-dev \
                    openssl graphviz python-all procps \
                    python-dev python-setuptools python-pip python3 python3.4 \
                    python-twisted-conch libtool git dh-autoreconf \
                    linux-headers-$(uname -r) libcap-ng-dev");
    os.system("sudo pip2 install six");

@when_not('openvswitch.installed')
def install_openvswitch():
    # Do your setup here.
    #
    # If your charm has other dependencies before it can install,
    # add those as @when() clauses above., or as additional @when()
    # decorated handlers below
    #
    # See the following for information about reactive charms:
    #
    #  * https://jujucharms.com/docs/devel/developer-getting-started
    #  * https://github.com/juju-solutions/layer-basic#overview
    #

    os.system("git clone https://github.com/openvswitch/ovs.git /tmp/ovs");

    os.chdir("/tmp/ovs");
    os.system("./boot.sh");
    os.system("./configure --prefix=/usr --localstatedir=/var  --sysconfdir=/etc --enable-ssl --with-linux=/lib/modules/`uname -r`/build");
    os.system("make -j3 ; sudo make install ; sudo make modules_install");

    os.system("sudo mkdir /etc/depmod.d/");
    os.system("for module in datapath/linux/*.ko; do modname='$(basename ${module})' ; echo 'override ${modname%.ko} * extra' >> '/etc/depmod.d/openvswitch.conf' ; echo 'override ${modname%.ko} * weak-updates' >> '/etc/depmod.d/openvswitch.conf' ; done");
    os.system("/sbin/modprobe openvswitch");

    os.system("/usr/share/openvswitch/scripts/ovs-ctl start --system-id=$(uuidgen)");

    set_state('openvswitch.installed')

