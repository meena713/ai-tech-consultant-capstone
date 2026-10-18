import {test} from "node:test";
import assert from "node:assert/strict";
import {classify,normalize} from "./index";
test("refund classification",()=>assert.equal(classify("Payment","I want a refund"),"refund"));
test("how-to classification",()=>assert.equal(classify("Help","How do I change my profile?"),"how_to"));
test("changed reply differs",()=>assert.notEqual(normalize("Hello there"),normalize("Hello there!")));
test("outer whitespace is ignored",()=>assert.equal(normalize("  hello  "),normalize("hello")));
