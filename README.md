# Public Release YAOKI lunar rover data

On March 6th 2025, the Dymon YAOKI rover landed on the Moon aboard the Intuitive Machines IM-2 lander. 

The operations were conducted by JAOPS leveraging the open-source Yamcs Mission Control System. 

This repository publicly releases: 
- The Yamcs configuration used during the mission to receive all data. 
- The data received: telemetry from the rover, the lander telemetry that was shared with the rover, the images captured on the Moon. 
- the telecommands sent to the rover on the Moon


Note: the interface and Yamcs link between the YAOKI mission control center and the Intuitive Machine's Mission Control Center includes credential and proprietary information so that part has been removed from this release,


## Setup
1. Yamcs requires Java 17+, if not already installed on your system, use: 
```bash
sudo apt install -y openjdk-25-jdk maven
```
2. Copy the Yamcs database files
```bash
./data/setup_yamcs_data.sh 
```
3. Start the Yamcs server: 
```bash
cd im2-yaoki-yamcs-public/yamcs-server
mvn yamcs:run
```

You now have the same setup running as was used for the YAOKI mission!

## Usage
View the telemetry and command history via the Yamcs Web interface

1. go to http://localhost:8090
2. check the data in the [Archive Browser tab](http://localhost:8090/archive?c=im2-yaoki__realtime&start=2025-02-25T18:33:56.087Z&stop=2025-03-08T01:31:16.844Z&packets=true&parameters=true&commands=true&events=false) 
3. plot the telemetry items in the [Parameters tab](http://localhost:8090/telemetry/parameters/YAOKI/Lander/temperature0/-/chart?c=im2-yaoki__realtime&interval=CUSTOM&customStart=Sun%20Mar%2002%202025%2008:28:34%20GMT%2B0900%20(Japan%20Standard%20Time)&customStop=Mon%20Jun%2002%202025%2008:43:34%20GMT%2B0900%20(Japan%20Standard%20Time))

## Data Analysis

For deeper analysis, use the Yamcs Python API to retrieve the data and make plots. 
An example Jupyter notebook demonstrates this process
1. install the dependencies in a new virtual environment: 
```bash
cd im2-yaoki-yamcs-public
python3 -m venv .venv/yaoki
source venv/yaoki/bin/activate
pip install -r analysis/requirements.txt
```
2. Open VS Code and run the notebook: `analysis/yamcs_archive.ipynb`
3. Run the notebook cells, notice the functions to retrieve data from the Yamcs archive and to transform it and to plot it