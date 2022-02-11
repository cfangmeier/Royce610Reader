<p align="center">
<img src="https://github.com/cfangmeier/Royce610Reader/blob/master/logo.png?raw=true"></img>
</p>

`Royce610Reader` is an **unofficial** interface to collect results from Royce 610 wirebond pull-tester. It works by reading data coming over the RS232 interface that connects a Windows PC to the pull-tester.

![image](https://user-images.githubusercontent.com/2569566/153683423-dc509db2-3861-432a-bdf3-3dd737785bb7.png)


## Requirements

  - A Windows 10 PC. Other operating systems may work but have not been tested.
  - A Royce 610 Wirebond pull-tester
  - An RS232 Serial cable connecting the PC to the pull-tester

## Installation

The easiest way to get started is to just download the [latest release](https://github.com/cfangmeier/Royce610Reader/releases) which bundles everything you need in a single executable. You can also checkout the source code and run it if you have Python 3.8+ installed and the `pyserial`, `numpy`, and `matplotlib` packages installed.

## Setup

On the pull-tester, the setting called "RS232 EA TEST" must be set to true. Otherwise, default settings should work.

## Using the Program

Run it by simply double clicking on the executable. You will be presented with the main window. Select which COM port corresponds to the pull-tester and click connect. If the port can be opened, you will get a notification on the terminal window that opened along with the main window that monitoring has started. 

Next, you can just perform pull-testing as usual and results will automatically accumulate in the application. If you wish to save results when you are finished, click the "Save CSV" button and choose where you would like to save the results.
