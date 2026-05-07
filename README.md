# PE Inventory Forecasting Challenge

### Background

PE is an MSME organization that provides service and maintenance support for DG gensets used at mobile tower sites across multiple states in eastern India.

The company supports service and maintenance contracts for telecom operators. As part of this work, PE handles:

- regular servicing
- complaints and breakdown support
- preventive maintenance
- workshop consumption
- sale or issue of parts/items where required

PE currently uses an internal stock management system built using **.NET WebForms** and a **SQL Server database**.

The system allows the team to manage inventory through simple stock register operations.

### Current Stock Management Flow

The existing system captures stock movement through stock-in and stock-out entries.

### Stock In

Stock-in entries include:

- selected product/item
- quantity stocked in
- bill or invoice reference
- stock-in date and related details

### Stock Out

Stock-out entries are usually created through challans.

Stock-out may happen for:

- direct sale
- internal workshop consumption
- complaint work
- preventive maintenance work
- planned maintenance activity

Preventive maintenance and complaint work are linked to PE’s service contracts for DG gensets at telecom tower sites.

## Problem Statement

PE wants to maintain optimal inventory levels for the parts and items needed in its service operations.

The company has historical stock movement data and also has visibility into preventive maintenance or planned maintenance work where certain parts/items are expected to be required.

The challenge is to build a forecasting solution that can estimate future stock requirements using:

- historical stock movement
- stock-in and stock-out patterns
- preventive maintenance pipeline
- planned maintenance requirements

The goal is to help PE understand what stock they may need to keep available so they can reduce shortages, avoid overstocking, and improve planning.

## Requirement

A  forecasting workflow that can help PE estimate future stock requirements for its inventory items based on historical consumption and planned/preventive maintenance pipeline.

## Data Access

The dataset is not included publicly in this repository.

Contributors who want to work on this challenge can request access by contacting the maintainer by email.

Access will include one or more of the following:

- application access
- test credentials
- database backup or SQL Server database access
- sample exported data

Please contact:
[abhijeet@366pitech.com]
