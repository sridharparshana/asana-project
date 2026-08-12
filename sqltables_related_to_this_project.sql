-- stockandmanagement_prod.tbl_pushmycartusa_sales definition

CREATE TABLE `tbl_pushmycartusa_sales` (
  `idno` int NOT NULL AUTO_INCREMENT,
  `orderdate` datetime DEFAULT NULL,
  `ordernumber` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `lineitemkey` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `orderstatus` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `sku` varchar(50) DEFAULT NULL,
  `msku` varchar(20) DEFAULT '0',
  `item_name` varchar(1000) DEFAULT NULL,
  `quantity` int DEFAULT NULL,
  `packsize` int DEFAULT '0',
  `total_quantity` int GENERATED ALWAYS AS ((`quantity` * `packsize`)) STORED,
  `quantity_refunded` int DEFAULT NULL,
  `brandid` int DEFAULT '0',
  `unit_price_usd` decimal(10,2) DEFAULT NULL,
  `discountamount` decimal(10,2) DEFAULT NULL,
  `taxamount` decimal(10,2) DEFAULT NULL,
  `shippingpaid` decimal(10,2) DEFAULT NULL,
  `total_payment_usd` decimal(10,2) DEFAULT NULL,
  `payment_gateway` varchar(50) DEFAULT NULL,
  `financial_status` varchar(50) DEFAULT NULL,
  `fulfillment_date` datetime DEFAULT NULL,
  `trackingnumber` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `customerid` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `customername` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `customeremail` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `customerphone` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `shippingaddress1` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `address2` varchar(50) DEFAULT NULL,
  `city` varchar(50) DEFAULT NULL,
  `country` varchar(50) DEFAULT NULL,
  `createdat` datetime DEFAULT CURRENT_TIMESTAMP,
  `carrier_country` varchar(50) DEFAULT NULL,
  `carrier` varchar(50) DEFAULT NULL,
  `total_shipmentcost` decimal(10,2) DEFAULT NULL,
  `orderid` varchar(250) DEFAULT NULL,
  `chargeback` decimal(10,2) DEFAULT '0.00',
  `other_charges` decimal(10,2) DEFAULT '0.00',
  `trackingstatus` varchar(250) DEFAULT NULL,
  PRIMARY KEY (`idno`),
  UNIQUE KEY `tbl_pushmycartusa_sales_unique1` (`ordernumber`,`lineitemkey`,`sku`),
  KEY `idx_pushmycart_order_sku_status` (`ordernumber`,`sku`,`orderstatus`),
  KEY `idx_order_line` (`ordernumber`,`lineitemkey`)
) ENGINE=InnoDB AUTO_INCREMENT=1695739 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;




-- stockandmanagement_prod.tbl_pushmycartusa_orderstatus definition

CREATE TABLE `tbl_pushmycartusa_orderstatus` (
  `orderdate` datetime DEFAULT NULL,
  `ordernumber` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `lineitemkey` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `orderstatus` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `sku` varchar(50) DEFAULT NULL,
  `quantity` int DEFAULT NULL,
  `quantity_refunded` int DEFAULT NULL,
  `payment_gateway` varchar(50) DEFAULT NULL,
  `financial_status` varchar(50) DEFAULT NULL,
  `fulfillment_date` datetime DEFAULT NULL,
  `trackingnumber` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `createdat` datetime DEFAULT CURRENT_TIMESTAMP,
  `carrier` varchar(100) DEFAULT NULL,
  `trackingstatus` varchar(500) DEFAULT NULL,
  UNIQUE KEY `tbl_pushmycartusa_sales_unique1` (`ordernumber`,`lineitemkey`,`sku`),
  KEY `idx_order_line` (`ordernumber`,`lineitemkey`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;




-- stockandmanagement_prod.shipped_orders_header definition

CREATE TABLE `shipped_orders_header` (
  `ID` int NOT NULL AUTO_INCREMENT,
  `shipmentid` varchar(50) NOT NULL,
  `orderid` varchar(45) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL,
  `ordernumber` varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL,
  `shipdate` datetime DEFAULT NULL,
  `shipmentcost` float DEFAULT NULL,
  `trackingnumber` varchar(250) NOT NULL,
  `warehouseid` varchar(45) CHARACTER SET latin1 COLLATE latin1_swedish_ci DEFAULT NULL,
  `storeid` varchar(45) CHARACTER SET latin1 COLLATE latin1_swedish_ci DEFAULT NULL,
  `state` varchar(45) DEFAULT NULL,
  `postalCode` varchar(45) DEFAULT NULL,
  `taxAmount` float DEFAULT NULL,
  `shippingamount` float DEFAULT NULL,
  `totalamount` float DEFAULT NULL,
  `country` varchar(45) DEFAULT NULL,
  `phone` varchar(100) DEFAULT NULL,
  `city` varchar(100) DEFAULT NULL,
  `street1` varchar(1000) CHARACTER SET latin1 COLLATE latin1_swedish_ci DEFAULT NULL,
  `customername` varchar(100) DEFAULT NULL,
  `shipping_address` varchar(500) DEFAULT NULL,
  `Stamp` datetime DEFAULT CURRENT_TIMESTAMP,
  `servicecode` varchar(45) CHARACTER SET latin1 COLLATE latin1_swedish_ci DEFAULT NULL,
  `deliverystatus` varchar(100) CHARACTER SET latin1 COLLATE latin1_swedish_ci DEFAULT NULL,
  `label_creation_date` datetime DEFAULT NULL,
  `last_action_date` datetime DEFAULT NULL,
  `expected_delivery_date` datetime DEFAULT NULL,
  `delivered_date` datetime DEFAULT NULL,
  `modifiedon` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB AUTO_INCREMENT=512318 DEFAULT CHARSET=latin1;

