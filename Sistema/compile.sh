#!/bin/bash

tput setaf 7 ; tput setab 4 ; tput bold ; printf '%50s%s%-20s\n' "BadVPN, created By Mr.Devim" ; tput sgr0
if [ -f "/usr/local/bin/badvpn-udpgw" ]
then
	tput setaf 3 ; tput bold ; echo ""
	echo ""
	echo "BadVPN has already been successfully installed."
	echo "To execute, create a screen session"
	echo "And execute the command:"
	echo ""
	echo "badudp"
	echo ""
	echo "And leave the screen session running in the background."
	echo "" ; tput sgr0
	exit
else
tput setaf 2 ; tput bold ; echo ""
echo -e "\033[1;36mThis is a script that automatically compiles and installs the BadVPN program on Debian and Ubuntu servers to enable UDP forwarding on port 7300, used by programs like HTTP Injector from Evozi. Thus allowing the use of the UDP protocol for online games, VoIP calls and other interesting things.\033[0m"
echo "" ; tput sgr0
read -p "Do you want to continue? [y/n]: " -e -i n resposta
if [[ "$resposta" = 'y' ]]; then
	echo ""
	echo -e "\033[1;31mInstallation may take a while... be patient!\033[0m"
	sleep 3
	apt-get update -y
	apt-get install screen wget gcc build-essential g++ make -y
	wget http://www.cmake.org/files/v2.8/cmake-2.8.12.tar.gz
	tar xvzf cmake*.tar.gz
	cd cmake*
	./bootstrap --prefix=/usr
	make 
	make install
	cd ..
	rm -r cmake*
	mkdir badvpn-build
	cd badvpn-build
	wget https://github.com/ambrop72/badvpn/archive/refs/tags/1.999.130.tar.gz
	tar xf 1.999.130.tar.gz
	cd bad*
	cmake -DBUILD_NOTHING_BY_DEFAULT=1 -DBUILD_UDPGW=1
	make install
	cd ..
	rm -r bad*
	cd ..
	rm -r badvpn-build
    chmod +x badvpn.sh
    ./badvpn.sh
	echo "#!/bin/bash
	badvpn-udpgw --listen-addr 127.0.0.1:7300 --max-clients 512 --max-connections-for-client 8" > /bin/badudp
	chmod +x /bin/badudp
	clear
	tput setaf 3 ; tput bold ; echo ""
	echo ""
	echo -e "\033[1;36mBadVPN successfully installed. To use, create a screen session and execute the badudp command and leave the screen session running in the background.\033[0m"
	echo "" ; tput sgr0
	exit
else 
	echo ""
	exit
fi
fi
